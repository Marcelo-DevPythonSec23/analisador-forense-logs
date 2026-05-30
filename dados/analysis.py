import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    INFO = 1


class AttackPhase(Enum):
    RECONNAISSANCE = "Reconhecimento"
    INITIAL_ACCESS = "Acesso Inicial"
    EXECUTION = "Execução"
    PERSISTENCE = "Persistência"
    PRIVILEGE_ESCALATION = "Escalação de Privilégio"
    DEFENSE_EVASION = "Evasão de Defesa"
    CREDENTIAL_ACCESS = "Acesso a Credenciais"
    DISCOVERY = "Descoberta"
    LATERAL_MOVEMENT = "Movimento Lateral"
    COLLECTION = "Coleta"
    EXFILTRATION = "Exfiltração"
    IMPACT = "Impacto"


class LogType(Enum):
    SYSLOG = "syslog"
    APACHE = "apache"
    WINDOWS = "windows"
    FIREWALL = "firewall"
    IDS = "ids"
    DNS = "dns"
    AUTHENTICATION = "authentication"


@dataclass
class ForensicEvent:
    """
    Representa um evento de segurança parseado de um log normalizado.

    Um ForensicEvent é o objeto fundamental do pipeline. Cada evento carrega
    informações temporais, contexto de rede, usuário envolvido e severidade
    já classificada. Eventos são imutáveis após criação e servem como entrada
    para detecção de ameaças correlacionadas.
    """
    timestamp: datetime
    source_ip: str
    destination_ip: str
    event_type: str
    user: str
    command: Optional[str] = None
    status: str = "unknown"
    severity: ThreatLevel = ThreatLevel.INFO
    raw_log: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.severity, ThreatLevel):
            raise ValueError("severity deve ser ThreatLevel")


@dataclass
class ThreatIndicator:
    indicator_type: str
    indicator_value: str
    threat_level: ThreatLevel
    attack_phase: AttackPhase
    description: str
    confidence: int
    related_events: List[int]

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 100:
            raise ValueError("confidence deve estar entre 0 e 100")


@dataclass
class SecurityAlert:
    """
    Representa um alerta de segurança gerado pela análise forense.

    Um SecurityAlert encapsula a conclusão de que múltiplos ForensicEvents,
    quando correlacionados, indicam uma ameaça. Contém evidências, mapeamento
    MITRE ATT&CK, IoCs e recomendações de resposta.
    """
    alert_id: str
    title: str
    description: str
    threat_level: ThreatLevel
    attack_phase: AttackPhase
    indicators: List[ThreatIndicator]
    affected_assets: Dict[str, List[str]]
    recommendations: List[str]
    evidence: List[ForensicEvent]
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class AnalysisResult:
    file_path: str
    total_events: int
    total_alerts: int
    alerts: List[SecurityAlert]
    summary: Dict[str, Any]
    cti_report: str
    events: List[ForensicEvent]


class LogParser:
    """
    Responsável por parsing e normalização de logs de segurança.

    O LogParser lê arquivos CSV de diferentes formatos (syslog, Apache, Windows,
    firewall, IDS) e normaliza seus campos para um objeto ForensicEvent padrão.
    A normalização é essencial porque diferentes fontes usam nomes de coluna
    variados (host vs source_ip, nivel vs level vs severity).

    A severidade é inferida combinando event_type, status e message para capturar
    sinais que diferentes sistemas expressam de formas diferentes.

    Limitações:
    - Falhas de parsing são capturadas silenciosamente (com logging).
    - Assume formato CSV; outros formatos requerem pré-processamento.
    - Classificação de severidade pode gerar falsos positivos se logs contiverem
      palavras-chave enganosas.
    """
    def __init__(self, log_type: LogType = LogType.SYSLOG) -> None:
        self.log_type = log_type
        logger.info(f"Parser inicializado para tipo: {log_type.value}")

    def parse_csv_logs(self, file_path: str) -> List[ForensicEvent]:
        """Carrega um CSV e converte cada linha em ForensicEvent."""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Arquivo não encontrado: {file_path}")
            raise FileNotFoundError(file_path)

        df = pd.read_csv(path)
        logger.info(f"Carregado arquivo: {file_path} ({len(df)} registros)")

        events: List[ForensicEvent] = []
        for _, row in df.iterrows():
            event = self._parse_row(row)
            if event is not None:
                events.append(event)

        logger.info(f"{len(events)} eventos parseados com sucesso")
        return events

    def _parse_row(self, row: pd.Series) -> Optional[ForensicEvent]:
        """Normaliza uma linha do CSV e determina a severidade do evento."""
        try:
            row_data = {str(key).lower(): value for key, value in row.to_dict().items()}

            timestamp = pd.to_datetime(row_data.get("timestamp", datetime.utcnow()))
            source_ip = str(row_data.get("source_ip", row_data.get("host", "unknown")))
            destination_ip = str(row_data.get("destination_ip", row_data.get("dest_ip", "unknown")))
            event_type = str(
                row_data.get("event_type")
                or row_data.get("servico")
                or row_data.get("service")
                or row_data.get("host")
                or row_data.get("mensagem")
                or "unknown"
            )
            user = str(row_data.get("user", row_data.get("usuario", "unknown")))
            status = str(
                row_data.get("status")
                or row_data.get("nivel")
                or row_data.get("level")
                or row_data.get("severity")
                or "unknown"
            )
            message = str(row_data.get("mensagem", row_data.get("message", "")))

            # A severidade é inferida a partir de event_type/status/message.
            # Se houver "ERROR" ou "failed" no conteúdo, o nível será HIGH.
            severity = self._determine_severity(event_type, status, message)

            return ForensicEvent(
                timestamp=timestamp,
                source_ip=source_ip,
                destination_ip=destination_ip,
                event_type=event_type,
                user=user,
                command=row_data.get("command"),
                status=status,
                severity=severity,
                raw_log=str(row_data),
            )
        except Exception as exception:
            logger.warning(f"Falha ao parsear registro: {exception}")
            return None

    @staticmethod
    def _determine_severity(event_type: str, status: str, message: str = "") -> ThreatLevel:
        """
        Classifica severidade via palavras-chave com lógica em cascata.

        1. Busca palavras-chave explícitas (critical, error, warn, info).
           Se encontrado, retorna ThreatLevel associado (sem continuar).
        2. Padrões de ameaça implícita:
           - exploit/malware/ransomware/root/sudo não-falhados = CRITICAL
           - failed_login/unauthorized/denied/violation = HIGH
        3. Se nada encontrado, assume INFO (padrão seguro).

        Decisões de design:
        - ERROR mapeia para HIGH (não CRITICAL) porque "error" genérico é
          menos grave que "exploit" ou "failed_login" específicos.
        - "sudo" não-falhado = CRITICAL (elevação bem-sucedida).
          "sudo failed" = apenas HIGH (tentativa bloqueada).

        Falsos positivos conhecidos:
        - Logs mencionando "error" em contextos informativos serão HIGH.
        - Campos injetados podem gerar classificação incorreta.
        - "failed" em strings genéricas pode correlacionar incorretamente.
        """
        lowered = f"{event_type} {status} {message}".lower()

        explicit_severity = {
            "critical": ThreatLevel.CRITICAL,
            "crítico": ThreatLevel.CRITICAL,
            "critico": ThreatLevel.CRITICAL,
            "fatal": ThreatLevel.CRITICAL,
            "high": ThreatLevel.HIGH,
            "alto": ThreatLevel.HIGH,
            "error": ThreatLevel.HIGH,
            "erro": ThreatLevel.HIGH,
            "failed": ThreatLevel.HIGH,
            "warn": ThreatLevel.MEDIUM,
            "warning": ThreatLevel.MEDIUM,
            "medium": ThreatLevel.MEDIUM,
            "médio": ThreatLevel.MEDIUM,
            "medio": ThreatLevel.MEDIUM,
            "low": ThreatLevel.LOW,
            "baixo": ThreatLevel.LOW,
            "info": ThreatLevel.INFO,
            "informational": ThreatLevel.INFO,
        }

        # Passo 1: Buscar palavras-chave explícitas; primeira encontrada vence.
        for keyword, level in explicit_severity.items():
            if keyword in lowered:
                return level

        # Passo 2: Ameaças implícitas CRITICAL (exploits/privilégios bem-sucedidos).
        # "sudo" ou "exploit" falhado não é CRITICAL; sucesso é critério.
        if any(keyword in lowered for keyword in ["exploit", "malware", "ransomware", "root", "sudo"]):
            if "failed" not in status.lower():
                return ThreatLevel.CRITICAL

        # Passo 3: Ameaças implícitas HIGH (autenticação/autorização falhadas).
        # Mesmo bloqueadas, tentativas estruturadas indicam reconhecimento ou ataque.
        if any(keyword in lowered for keyword in ["failed_login", "unauthorized", "denied", "violation"]):
            return ThreatLevel.HIGH

        # Padrão seguro: INFO se nenhum indicador detectado.
        return ThreatLevel.INFO


class ForensicAnalyzer:
    def __init__(self) -> None:
        self.events: List[ForensicEvent] = []
        self.alerts: List[SecurityAlert] = []
        self.indicators: List[ThreatIndicator] = []
        logger.info("ForensicAnalyzer inicializado")

    def load_events(self, events: List[ForensicEvent]) -> None:
        self.events = events
        logger.info(f"Carregados {len(events)} eventos para análise")

    def detect_brute_force(self, threshold: int = 5) -> List[SecurityAlert]:
        # Detector de brute force: identifica (IP, usuario) com multiplas falhas login.
        # Threshold=5 foi escolhido para balancear falsos positivos (usuarios que
        # esquecem senha) vs falsos negativos (ataques lentos/automatizados).
        alerts: List[SecurityAlert] = []
        brute_force_candidates: Dict[Any, List[ForensicEvent]] = {}

        for event in self.events:
            if "failed" in event.status.lower() and "login" in event.event_type.lower():
                key = (event.source_ip, event.user)
                brute_force_candidates.setdefault(key, []).append(event)

        for (source_ip, user), failed_events in brute_force_candidates.items():
            if len(failed_events) >= threshold:
                alert = SecurityAlert(
                    alert_id=f"BF-{source_ip}-{user}",
                    title="Potencial Ataque Brute Force Detectado",
                    description=f"{len(failed_events)} tentativas de login falhadas de {source_ip} para usuário {user}",
                    threat_level=ThreatLevel.HIGH,
                    attack_phase=AttackPhase.INITIAL_ACCESS,
                    indicators=[
                        ThreatIndicator(
                            indicator_type="IP",
                            indicator_value=source_ip,
                            threat_level=ThreatLevel.HIGH,
                            attack_phase=AttackPhase.INITIAL_ACCESS,
                            description="IP atacante detectado",
                            confidence=85,
                            related_events=list(range(len(failed_events))),
                        )
                    ],
                    affected_assets={"users": [user], "source_ips": [source_ip]},
                    recommendations=[
                        "Bloquear IP de origem imediatamente",
                        "Forçar reset de senha do usuário",
                        "Revisar histórico de acesso da conta",
                        "Aplicar rate limiting para conexões suspeitas",
                    ],
                    evidence=failed_events,
                )
                alerts.append(alert)
                self.alerts.append(alert)
                logger.warning(f"Brute force detectado para {source_ip} -> {user}")

        return alerts

    def detect_privilege_escalation(self) -> List[SecurityAlert]:
        # Detector de escalacao de privilegio: busca comandos sudo ou mencoes em event_type.
        # Limitacao: classifica qualquer uso de sudo como suspeito (nao diferencia
        # sucesso vs falha, ou uso legitimo vs ataque).
        alerts: List[SecurityAlert] = []
        escalation_events = [
            event for event in self.events
            if event.command and "sudo" in event.command.lower()
            or "privilege" in event.event_type.lower()
        ]

        if escalation_events:
            alert = SecurityAlert(
                alert_id="ESC-001",
                title="Atividade de Escalação de Privilégio Detectada",
                description=f"{len(escalation_events)} eventos suspeitos de escalação de privilégio",
                threat_level=ThreatLevel.HIGH,
                attack_phase=AttackPhase.PRIVILEGE_ESCALATION,
                indicators=[
                    ThreatIndicator(
                        indicator_type="COMMAND",
                        indicator_value="sudo",
                        threat_level=ThreatLevel.MEDIUM,
                        attack_phase=AttackPhase.PRIVILEGE_ESCALATION,
                        description="Uso de comando privilegiado detectado",
                        confidence=75,
                        related_events=[i for i, _ in enumerate(escalation_events)],
                    )
                ],
                affected_assets={"users": list({event.user for event in escalation_events})},
                recommendations=[
                    "Auditar comandos executados",
                    "Verificar se a execução foi autorizada",
                    "Reforçar controles de acesso privilegiado",
                ],
                evidence=escalation_events,
            )
            alerts.append(alert)
            self.alerts.append(alert)
            logger.warning("Escalação de privilégio detectada")

        return alerts

    def detect_suspicious_ips(self) -> List[SecurityAlert]:
        # Detector de IP suspeito por correlacao: agrega atividade por source_ip.
        # Criterios de alerta (qualquer um ativa):\n        # 1. >50 eventos: volume anomalo indica atividade estruturada.\n        # 2. >5 usuarios unicos: movimento lateral ou reconhecimento.\n        # 3. >0 CRITICAL: IP que originou evento critico eh marcado criticamente.\n        # Limitacoes: nao diferencia NAT/Proxy/Legit; sem baseline temporal.\n        alerts: List[SecurityAlert] = []
        ip_activity: Dict[str, Dict[str, Any]] = {}

        for event in self.events:
            entry = ip_activity.setdefault(event.source_ip, {"users": set(), "events": 0, "critical": 0})
            entry["users"].add(event.user)
            entry["events"] += 1
            entry["critical"] += 1 if event.severity == ThreatLevel.CRITICAL else 0

        for ip, stats in ip_activity.items():
            if stats["events"] > 50 or len(stats["users"]) > 5 or stats["critical"] > 0:
                level = ThreatLevel.CRITICAL if stats["critical"] > 0 else ThreatLevel.HIGH
                alert = SecurityAlert(
                    alert_id=f"SUSP-{ip}",
                    title=f"Atividade Suspeita de IP Detectada: {ip}",
                    description=(
                        f"IP {ip} com {stats['events']} eventos, "
                        f"{len(stats['users'])} usuários únicos"
                    ),
                    threat_level=level,
                    attack_phase=AttackPhase.LATERAL_MOVEMENT,
                    indicators=[
                        ThreatIndicator(
                            indicator_type="IP",
                            indicator_value=ip,
                            threat_level=level,
                            attack_phase=AttackPhase.LATERAL_MOVEMENT,
                            description="IP com atividade suspeita detectada",
                            confidence=80,
                            related_events=[],
                        )
                    ],
                    affected_assets={"source_ips": [ip], "target_users": list(stats["users"])},
                    recommendations=[
                        "Investigar origem do IP",
                        "Bloquear IP suspeito",
                        "Auditar contas e conexões afetadas",
                        "Monitorar atividade adicional no IP",
                    ],
                    evidence=[],
                )
                alerts.append(alert)
                self.alerts.append(alert)
                logger.warning(f"IP suspeito detectado: {ip}")

        return alerts

    def generate_timeline(self) -> pd.DataFrame:
        rows = [
            {
                "timestamp": event.timestamp,
                "source_ip": event.source_ip,
                "user": event.user,
                "event_type": event.event_type,
                "status": event.status,
                "severity": event.severity.name,
                "description": f"{event.event_type} by {event.user} from {event.source_ip}",
            }
            for event in self.events
        ]
        timeline = pd.DataFrame(rows)
        timeline = timeline.sort_values("timestamp")
        logger.info(f"Timeline gerada com {len(timeline)} eventos")
        return timeline

    def calculate_event_severity_counts(self) -> Dict[str, int]:
        """Conta quantos eventos existem em cada nível ThreatLevel."""
        counts = {
            ThreatLevel.CRITICAL.name: 0,
            ThreatLevel.HIGH.name: 0,
            ThreatLevel.MEDIUM.name: 0,
            ThreatLevel.LOW.name: 0,
            ThreatLevel.INFO.name: 0,
        }
        for event in self.events:
            counts[event.severity.name] += 1
        return counts

    def generate_report(self) -> Dict[str, Any]:
        """Gera o relatório final com contagem de eventos e alertas."""
        severity_counts = self.calculate_event_severity_counts()
        report = {
            "summary": {
                "total_events": len(self.events),
                "total_alerts": len(self.alerts),
                "critical_alerts": sum(1 for alert in self.alerts if alert.threat_level == ThreatLevel.CRITICAL),
                "high_alerts": sum(1 for alert in self.alerts if alert.threat_level == ThreatLevel.HIGH),
                "severity_counts": severity_counts,
            },
            "alerts": [
                {
                    "id": alert.alert_id,
                    "title": alert.title,
                    "threat_level": alert.threat_level.name,
                    "attack_phase": alert.attack_phase.value,
                    "evidence_count": len(alert.evidence),
                    "recommendations": alert.recommendations,
                }
                for alert in self.alerts
            ],
            "timeline": self.generate_timeline().to_dict(orient="records"),
            "generated_at": datetime.utcnow().isoformat(),
        }
        logger.info("Relatório de análise gerado")
        return report


class CTIAnalyzer:
    ATTACK_PATTERNS = {
        "credential_stuffing": {
            "keywords": ["failed_login", "invalid_password"],
            "phase": AttackPhase.CREDENTIAL_ACCESS,
            "severity": ThreatLevel.HIGH,
            "description": "Tentativas de credential stuffing detectadas",
        },
        "lateral_movement": {
            "keywords": ["lateral", "pivot", "move", "lateral_move"],
            "phase": AttackPhase.LATERAL_MOVEMENT,
            "severity": ThreatLevel.HIGH,
            "description": "Atividade de movimento lateral detectada",
        },
        "data_exfiltration": {
            "keywords": ["exfiltration", "data_transfer", "bulk_transfer"],
            "phase": AttackPhase.EXFILTRATION,
            "severity": ThreatLevel.CRITICAL,
            "description": "Potencial exfiltração de dados detectada",
        },
        "persistence": {
            "keywords": ["cron", "scheduled_task", "registry", "startup"],
            "phase": AttackPhase.PERSISTENCE,
            "severity": ThreatLevel.HIGH,
            "description": "Tentativa de estabelecer persistência detectada",
        },
    }

    def __init__(self) -> None:
        logger.info("CTIAnalyzer inicializado")

    def map_to_mitre_attack(self, events: List[ForensicEvent]) -> Dict[str, List[ForensicEvent]]:
        mapping: Dict[str, List[ForensicEvent]] = {phase.value: [] for phase in AttackPhase}
        for event in events:
            for config in self.ATTACK_PATTERNS.values():
                if any(keyword in event.event_type.lower() for keyword in config["keywords"]):
                    mapping[config["phase"].value].append(event)
        logger.info("Eventos mapeados para MITRE ATT&CK")
        return mapping

    def identify_apt_indicators(self, events: List[ForensicEvent]) -> Dict[str, Any]:
        apt: Dict[str, Any] = {
            "living_off_the_land": False,
            "obfuscation_detected": False,
            "lateral_movement_pattern": False,
            "command_and_control": False,
            "data_staging": False,
            "confidence_score": 0,
        }

        raw_text = json.dumps([event.event_type for event in events]).lower()
        if any(tool in raw_text for tool in ["powershell", "wmi", "tasklist", "whoami", "net", "ping"]):
            apt["living_off_the_land"] = True
            apt["confidence_score"] += 20

        ip_users = {}
        for event in events:
            ip_users.setdefault(event.source_ip, set()).add(event.user)

        if any(len(users) > 3 for users in ip_users.values()):
            apt["lateral_movement_pattern"] = True
            apt["confidence_score"] += 30

        unusual_hours = [event for event in events if event.timestamp.hour < 6 or event.timestamp.hour > 22]
        if len(unusual_hours) > len(events) * 0.3:
            apt["command_and_control"] = True
            apt["confidence_score"] += 25

        logger.info(f"Análise APT concluída com score={apt['confidence_score']}")
        return apt

    def generate_cti_report(self, events: List[ForensicEvent]) -> str:
        mapping = self.map_to_mitre_attack(events)
        apt = self.identify_apt_indicators(events)

        report = [
            "# Cyber Threat Intelligence Report",
            f"**Gerado em:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Resumo Executivo",
            f"- Total de eventos: {len(events)}",
            f"- Indicadores APT detectados: {'SIM' if apt['confidence_score'] > 50 else 'NÃO'}",
            f"- Score de confiança: {apt['confidence_score']}%",
            "",
            "## Mapeamento MITRE ATT&CK",
        ]

        for phase_name, phase_events in mapping.items():
            if phase_events:
                report.extend([
                    f"### {phase_name}",
                    f"- Eventos detectados: {len(phase_events)}",
                    f"- Usuários únicos: {len(set(event.user for event in phase_events))}",
                    f"- IPs únicos: {len(set(event.source_ip for event in phase_events))}",
                    "",
                ])

        report.extend([
            "## Indicadores de APT",
            "| Indicador | Status |",
            "|---|---|",
            f"| Living off the Land | {'🔴 DETECTADO' if apt['living_off_the_land'] else '✅ OK'} |",
            f"| Ofuscação | {'🔴 DETECTADA' if apt['obfuscation_detected'] else '✅ OK'} |",
            f"| Movimento Lateral | {'🔴 DETECTADO' if apt['lateral_movement_pattern'] else '✅ OK'} |",
            f"| Comunicação C2 | {'🔴 DETECTADO' if apt['command_and_control'] else '✅ OK'} |",
            f"| Data Staging | {'🔴 DETECTADO' if apt['data_staging'] else '✅ OK'} |",
            "",
            "## Recomendações",
            "1. Isolar sistemas afetados",
            "2. Bloquear IPs suspeitos",
            "3. Auditoria de credenciais e atividades",
            "4. Implementar monitoramento contínuo",
        ])

        return "\n".join(report)


class AnalysisService:
    def __init__(self) -> None:
        self.cti = CTIAnalyzer()

    @staticmethod
    def infer_log_type(file_path: str) -> LogType:
        suffix = Path(file_path).suffix.lower()
        if suffix == ".csv":
            return LogType.SYSLOG
        if suffix in {".log", ".txt"}:
            return LogType.SYSLOG
        return LogType.SYSLOG

    def analyze_file(self, file_path: str) -> AnalysisResult:
        parser = LogParser(self.infer_log_type(file_path))
        events = parser.parse_csv_logs(file_path)

        forensic = ForensicAnalyzer()
        forensic.load_events(events)
        forensic.detect_brute_force()
        forensic.detect_privilege_escalation()
        forensic.detect_suspicious_ips()

        summary = forensic.generate_report()
        cti_report = self.cti.generate_cti_report(events)

        return AnalysisResult(
            file_path=file_path,
            total_events=len(events),
            total_alerts=len(forensic.alerts),
            alerts=forensic.alerts,
            summary=summary,
            cti_report=cti_report,
            events=events,
        )

    @staticmethod
    def serialize_report(result: AnalysisResult) -> str:
        payload = {
            "file_path": result.file_path,
            "total_events": result.total_events,
            "total_alerts": result.total_alerts,
            "summary": result.summary,
            "generated_at": datetime.utcnow().isoformat(),
        }
        return json.dumps(payload, indent=2, default=str)
