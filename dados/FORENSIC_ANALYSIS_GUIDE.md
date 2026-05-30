# 🔍 Guia Completo: Análise Forense & Cyber Threat Intelligence

## 📚 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [Componentes](#componentes)
4. [Como Usar](#como-usar)
5. [Exemplos Práticos](#exemplos-práticos)
6. [Referência de API](#referência-de-api)
7. [Engenharia de Software](#engenharia-de-software)

---

## 🎯 Visão Geral

A ferramenta de **Análise Forense & CTI** é um sistema profissional para:

- ✅ **Análise Forense**: Parse e análise de logs de segurança
- ✅ **Detecção de Ameaças**: Identificar padrões de ataque em tempo real
- ✅ **Cyber Threat Intelligence**: Mapear atividades para MITRE ATT&CK
- ✅ **Relatórios Executivos**: Gerar relatórios estruturados em JSON/Markdown
- ✅ **Análise de APT**: Identificar indicadores de Advanced Persistent Threat

---

## 🏗️ Arquitetura

### Visão Geral do Sistema

```
┌──────────────────────────────────────────────────────────┐
│         FORENSIC ANALYSIS & CTI SYSTEM                  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Input: Logs (CSV, Syslog, Windows, Firewall, IDS)     │
│    │                                                     │
│    ▼                                                     │
│  ┌──────────────┐                                       │
│  │  LogParser   │─── Valida & Normaliza                │
│  └──────────────┘                                       │
│    │                                                     │
│    ▼                                                     │
│  ┌──────────────────────┐                              │
│  │ ForensicAnalyzer     │─── Detecta ameaças            │
│  │ • Brute Force        │                              │
│  │ • Privilege Escalation│                             │
│  │ • Suspicious IPs     │                              │
│  │ • Timeline           │                              │
│  └──────────────────────┘                              │
│    │                                                     │
│    ▼                                                     │
│  ┌──────────────────────┐                              │
│  │ CTIAnalyzer          │─── Análise de Inteligência    │
│  │ • MITRE ATT&CK       │                              │
│  │ • APT Indicators     │                              │
│  │ • Recommendations    │                              │
│  └──────────────────────┘                              │
│    │                                                     │
│    ▼                                                     │
│  Output: Alertas + Relatórios                          │
│  • SecurityAlert (JSON)                                 │
│  • Timeline (CSV)                                       │
│  • CTI Report (Markdown)                               │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 🔧 Componentes

### 1. LogParser

**Responsabilidade**: Parse e normalização de logs

```python
class LogParser:
    def __init__(self, log_type: LogType) -> None
    def parse_csv_logs(self, file_path: str) -> List[ForensicEvent]
    def _parse_row(self, row: pd.Series) -> Optional[ForensicEvent]
    @staticmethod
    def _determine_severity(event_type: str, status: str) -> ThreatLevel
```

**Tipos Suportados**:
- SYSLOG
- APACHE
- WINDOWS
- FIREWALL
- IDS
- DNS
- AUTHENTICATION

**Validações**:
- Parsing de timestamps
- Validação de IPs
- Determinação automática de severidade

---

### 2. ForensicAnalyzer

**Responsabilidade**: Análise forense avançada

```python
class ForensicAnalyzer:
    def load_events(self, events: List[ForensicEvent]) -> None
    def detect_brute_force(self, threshold: int = 5) -> List[SecurityAlert]
    def detect_privilege_escalation(self) -> List[SecurityAlert]
    def detect_suspicious_ips(self) -> List[SecurityAlert]
    def generate_timeline(self) -> pd.DataFrame
    def generate_report(self) -> Dict[str, Any]
```

**Detecções Implementadas**:

1. **Brute Force**
   - Agrupa tentativas de login falhadas
   - Associa a IP e usuário
   - Gera alerta quando threshold é atingido

2. **Escalação de Privilégio**
   - Detecta comandos sudo
   - Detecta comandos de privilégio
   - Correlaciona com usuários

3. **IPs Suspeitos**
   - Identifica múltiplas conexões de um IP
   - Detecta múltiplos usuários por IP
   - Correlaciona com eventos críticos

---

### 3. CTIAnalyzer

**Responsabilidade**: Análise de Cyber Threat Intelligence

```python
class CTIAnalyzer:
    def map_to_mitre_attack(self, events: List[ForensicEvent]) 
        -> Dict[str, List[ForensicEvent]]
    def identify_apt_indicators(self, events: List[ForensicEvent]) 
        -> Dict[str, Any]
    def generate_cti_report(self, events: List[ForensicEvent]) -> str
```

**Mapeamento MITRE ATT&CK**:
- RECONNAISSANCE
- INITIAL_ACCESS
- EXECUTION
- PERSISTENCE
- PRIVILEGE_ESCALATION
- DEFENSE_EVASION
- CREDENTIAL_ACCESS
- DISCOVERY
- LATERAL_MOVEMENT
- COLLECTION
- EXFILTRATION
- IMPACT

**Análise de APT**:
- Living off the Land (uso de ferramentas legítimas)
- Ofuscação detectada
- Padrão de movimento lateral
- Comunicação C2
- Data staging
- Score de confiança

---

## 💻 Como Usar

### Importação

```python
from dados.analysis import (
    LogParser, ForensicAnalyzer, CTIAnalyzer,
    LogType, ThreatLevel, AttackPhase,
    ForensicEvent, SecurityAlert, ThreatIndicator
)
```

### Severidade e Níveis de Log

O parser detecta severidade tanto por campos de status quanto por campos de nível, incluindo variantes em português e inglês.

- `CRITICAL`, `crítico`, `critico`, `fatal` → `ThreatLevel.CRITICAL`
- `ERROR`, `ERRO`, `failed` → `ThreatLevel.HIGH`
- `WARN`, `WARNING`, `MEDIUM`, `MÉDIO` → `ThreatLevel.MEDIUM`
- `LOW`, `BAIXO` → `ThreatLevel.LOW`
- `INFO`, `informational` → `ThreatLevel.INFO`

O código trata automaticamente arquivos CSV com colunas como `timestamp`, `host`, `servico`, `nivel`, `mensagem`.

### Uso Básico

```python
# 1. Parse de logs
parser = LogParser(LogType.SYSLOG)
events = parser.parse_csv_logs("security_logs.csv")

# 2. Análise forense
analyzer = ForensicAnalyzer()
analyzer.load_events(events)

# Detectar ameaças
brute_force_alerts = analyzer.detect_brute_force(threshold=5)
escalation_alerts = analyzer.detect_privilege_escalation()
suspicious_ip_alerts = analyzer.detect_suspicious_ips()

# 3. Análise CTI
cti = CTIAnalyzer()
mitre_mapping = cti.map_to_mitre_attack(events)
apt_analysis = cti.identify_apt_indicators(events)
cti_report = cti.generate_cti_report(events)

# 4. Gerar relatório
timeline = analyzer.generate_timeline()
report = analyzer.generate_report()
```

---

## 📋 Exemplos Práticos

### Exemplo 1: Análise de Arquivo CSV

```python
# Arquivo: security_logs.csv
# Colunas: timestamp, source_ip, destination_ip, event_type, user, command, status

parser = LogParser(LogType.SYSLOG)
events = parser.parse_csv_logs("security_logs.csv")

print(f"Parseados {len(events)} eventos")

# Cada evento é um ForensicEvent com:
# - timestamp (datetime)
# - source_ip (str)
# - user (str)
# - severity (ThreatLevel)
```

### Exemplo 2: Detectar Brute Force

```python
analyzer = ForensicAnalyzer()
analyzer.load_events(events)

# Detectar tentativas de brute force
alerts = analyzer.detect_brute_force(threshold=5)

for alert in alerts:
    print(f"Alert: {alert.title}")
    print(f"Severity: {alert.threat_level.name}")
    print(f"Attack Phase: {alert.attack_phase.value}")
    print(f"Affected Users: {alert.affected_assets['users']}")
    print(f"Recommendations: {alert.recommendations}")
```

### Exemplo 3: Mapear para MITRE ATT&CK

```python
cti = CTIAnalyzer()

# Mapear eventos para fases de ataque
mitre_mapping = cti.map_to_mitre_attack(events)

for phase, phase_events in mitre_mapping.items():
    if phase_events:
        print(f"{phase}: {len(phase_events)} eventos detectados")
```

### Exemplo 4: Gerar Relatório Completo

```python
# Análise completa
analyzer.load_events(events)
analyzer.detect_brute_force()
analyzer.detect_privilege_escalation()
analyzer.detect_suspicious_ips()

# Gerar relatório
report = analyzer.generate_report()

print(f"Total de alertas: {report['summary']['total_alerts']}")
print(f"Alertas críticos: {report['summary']['critical_alerts']}")
print(f"Alertas de alta severidade: {report['summary']['high_alerts']}")

# Gerar timeline
timeline = analyzer.generate_timeline()
timeline.to_csv("timeline.csv")

# Gerar relatório CTI
cti_report = cti.generate_cti_report(events)
with open("cti_report.md", "w") as f:
    f.write(cti_report)
```

---

## 🔌 Referência de API

### Enums

```python
class ThreatLevel(Enum):
    CRITICAL = 5   # 🔴
    HIGH = 4       # 🟠
    MEDIUM = 3     # 🟡
    LOW = 2        # 🔵
    INFO = 1       # ⚪

class AttackPhase(Enum):
    RECONNAISSANCE
    INITIAL_ACCESS
    EXECUTION
    PERSISTENCE
    PRIVILEGE_ESCALATION
    DEFENSE_EVASION
    CREDENTIAL_ACCESS
    DISCOVERY
    LATERAL_MOVEMENT
    COLLECTION
    EXFILTRATION
    IMPACT

class LogType(Enum):
    SYSLOG
    APACHE
    WINDOWS
    FIREWALL
    IDS
    DNS
    AUTHENTICATION
```

### Dataclasses

#### ForensicEvent

```python
@dataclass
class ForensicEvent:
    timestamp: datetime
    source_ip: str
    destination_ip: str
    event_type: str
    user: str
    command: Optional[str] = None
    status: str = "unknown"
    severity: ThreatLevel = ThreatLevel.INFO
    raw_log: Optional[str] = None
```

#### ThreatIndicator

```python
@dataclass
class ThreatIndicator:
    indicator_type: str         # IP, Domain, Hash, Email, etc
    indicator_value: str        # 192.168.1.1, evil.com, etc
    threat_level: ThreatLevel
    attack_phase: AttackPhase
    description: str
    confidence: int             # 0-100
    related_events: List[int]
```

#### SecurityAlert

```python
@dataclass
class SecurityAlert:
    alert_id: str
    title: str
    description: str
    threat_level: ThreatLevel
    attack_phase: AttackPhase
    indicators: List[ThreatIndicator]
    affected_assets: Dict[str, List[str]]
    recommendations: List[str]
    evidence: List[ForensicEvent]
    created_at: datetime
```

---

## 🛠️ Engenharia de Software

### Princípios Aplicados

✅ **Type Hints Completos**
- Todos os parâmetros e retornos tipados
- Facilita IDE autocomplete
- Melhora detectabilidade de erros

✅ **Docstrings Profissionais**
- Google-style docstrings
- Descrição de Args e Returns
- Documentação de exceções

✅ **Validação de Entrada**
- Validação em `__post_init__` de dataclasses
- Validação de ranges (ex: confidence 0-100)
- Tratamento de tipos inválidos

✅ **Tratamento de Erros**
- Try/except em métodos críticos
- Logging de erros
- Mensagens descritivas

✅ **Logging Estruturado**
- Níveis: INFO, WARNING, ERROR
- Timestamps automáticos
- Emojis para fácil identificação

✅ **Arquitetura Modular**
- Separação de conceitos
- Classes com responsabilidades únicas
- Fácil extensão e manutenção

✅ **Testes Unitários**
- 5 testes automatizados
- Cobertura de componentes principais
- Validação de fluxos críticos

---

## 📊 Estrutura de Dados

### ForensicEvent

```
{
    "timestamp": "2026-05-28T18:31:24",
    "source_ip": "203.0.113.45",
    "destination_ip": "10.0.0.1",
    "event_type": "failed_login",
    "user": "admin",
    "command": null,
    "status": "failed",
    "severity": "HIGH"
}
```

### SecurityAlert

```json
{
    "alert_id": "BF-203.0.113.45-admin",
    "title": "🔴 Potencial Ataque Brute Force Detectado",
    "threat_level": "HIGH",
    "attack_phase": "Acesso Inicial",
    "indicators": [...],
    "affected_assets": {
        "users": ["admin"],
        "source_ips": ["203.0.113.45"]
    },
    "recommendations": [
        "Bloquear IP de origem imediatamente",
        "Forçar reset de senha do usuário",
        ...
    ]
}
```

---

## 🔐 Segurança

### Boas Práticas

- ✅ Validação de entrada em todos os pontos
- ✅ Logging sem exposição de dados sensíveis
- ✅ Tratamento robusto de exceções
- ✅ Type hints para prevenir type confusion

### Conformidade

- ✅ MITRE ATT&CK Framework
- ✅ Padrões de análise forense
- ✅ Boas práticas de CTI
- ✅ ISO 27035 (Incident Management)

---

## 📚 Referências

- [MITRE ATT&CK Framework](https://attack.mitre.org)
- [Cyber Threat Intelligence](https://www.gartner.com/en/topics/threat-intelligence)
- [Forensic Analysis](https://en.wikipedia.org/wiki/Digital_forensics)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

---

**Última atualização**: 28 de maio de 2026  
**Versão**: 1.0  
**Status**: ✅ Pronto para Produção
