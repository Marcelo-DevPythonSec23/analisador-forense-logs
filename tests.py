#!/usr/bin/env python3
"""
Script de Teste - Valida a estrutura e funcionalidade do Bot
Este script testa os componentes sem necessidade de um token real do Telegram
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Testa se todos os imports funcionam"""
    print("\n" + "="*80)
    print("🧪 TESTE 1: Validar Imports")
    print("="*80)
    
    try:
        from telegram import Update
        print("✅ telegram.Update importado com sucesso")
        
        from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
        print("✅ telegram.ext importado com sucesso")
        
        import os
        import logging
        from pathlib import Path
        from dotenv import load_dotenv
        print("✅ Módulos auxiliares importados com sucesso")

        from dados.analysis import AnalysisService, LogType
        from bot.database import DatabaseManager, SupportDatabaseManager
        print("✅ Módulos de análise e banco de dados importados com sucesso")
        
        return True
    except ImportError as e:
        print(f"❌ Erro ao importar: {e}")
        return False


def test_env_file():
    """Testa se o arquivo .env pode ser carregado"""
    print("\n" + "="*80)
    print("🧪 TESTE 2: Validar Arquivo .env")
    print("="*80)
    
    try:
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        token = os.getenv("TELEGRAM_TOKEN")
        
        if token:
            print("✅ Arquivo .env carregado")
            print(f"   Token configurado: {token[:10]}...")
        else:
            print("⚠️  Arquivo .env existe, mas TELEGRAM_TOKEN não está configurado")
            print("   (Isso é normal em ambiente de teste)")
        
        return True
    except Exception as e:
        print(f"❌ Erro ao carregar .env: {e}")
        return False


def test_directory_structure():
    """Testa a estrutura de diretórios"""
    print("\n" + "="*80)
    print("🧪 TESTE 3: Validar Estrutura de Diretórios")
    print("="*80)
    
    try:
        from pathlib import Path
        
        # Verifica diretórios esperados
        checks = {
            "bot/": Path("bot").is_dir(),
            "dados/": Path("dados").is_dir(),
        }
        
        all_ok = True
        for dir_name, exists in checks.items():
            status = "✅" if exists else "⚠️"
            print(f"{status} Diretório '{dir_name}': {'Existe' if exists else 'Não existe'}")
            if not exists:
                all_ok = False
        
        # Verifica arquivos esperados
        print("\nArquivos encontrados:")
        files = {
            "bot/bot.py": Path("bot/bot.py").is_file(),
            "requirements.txt": Path("requirements.txt").is_file(),
            ".env.example": Path(".env.example").is_file(),
            "README.md": Path("README.md").is_file(),
        }
        
        for file_name, exists in files.items():
            status = "✅" if exists else "❌"
            print(f"{status} Arquivo '{file_name}': {'Existe' if exists else 'Falta'}")
            if not exists:
                all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"❌ Erro ao validar estrutura: {e}")
        return False


def test_analysis_and_database():
    """Testa a integração de análise e persistência em banco de dados"""
    print("\n" + "="*80)
    print("🧪 TESTE 4: Validar Análise e Banco de Dados")
    print("="*80)

    try:
        import tempfile
        from pathlib import Path
        from dados.analysis import AnalysisService
        from bot.database import DatabaseManager, SupportDatabaseManager

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            csv_path = temp_path / "sample.csv"
            csv_path.write_text(
                "timestamp,source_ip,destination_ip,event_type,user,status,command\n"
                "2026-01-01 10:00:00,192.168.0.1,10.0.0.1,failed_login,admin,failed,ssh\n"
            )

            analysis = AnalysisService().analyze_file(str(csv_path))
            assert analysis.total_events == 1
            assert analysis.total_alerts >= 0

            db = DatabaseManager(temp_path / "monitoring.db")
            file_id = db.add_file_record(
                filename="sample.csv",
                file_path=str(csv_path),
                uploader_id="test-user",
                file_type=".csv",
            )
            db.update_file_analysis(file_id, analysis.summary, analysis.total_alerts)
            files = db.list_files()
            assert len(files) == 1

            support_db = SupportDatabaseManager(temp_path / "support.db")
            request_id = support_db.create_request(
                user_id="test-user",
                request_text="Solicitação de análise",
                problem_description="Não consigo validar o log CSV",
            )
            assert request_id > 0

        print("✅ Teste de análise e banco de dados passou")
        return True
    except AssertionError as e:
        print(f"❌ Teste de análise e banco de dados falhou: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro no teste de análise e banco de dados: {e}")
        return False


def test_bot_syntax():
    """Testa a sintaxe do arquivo bot.py e bot/app.py"""
    print("\n" + "="*80)
    print("🧪 TESTE 5: Validar Sintaxe dos Arquivos do Bot")
    print("="*80)
    
    try:
        import py_compile
        
        py_compile.compile("bot/bot.py", doraise=True)
        py_compile.compile("bot/app.py", doraise=True)
        print("✅ Sintaxe de bot/bot.py e bot/app.py é válida")
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ Erro de sintaxe: {e}")
        return False


def test_code_structure():
    """Testa se o arquivo bot/app.py contém as funções esperadas"""
    print("\n" + "="*80)
    print("🧪 TESTE 6: Validar Estrutura do bot/app.py")
    print("="*80)
    
    try:
        import ast
        
        with open("bot/app.py", "r") as f:
            tree = ast.parse(f.read())
        
        # Extrai nomes de funções definidas
        functions = [
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        ]
        
        expected_functions = ["start", "help_command", "status", "receber_arquivo", "handle_message", "issue", "list_files", "list_issues", "main"]
        
        print("Funções encontradas no bot/app.py:")
        for func in expected_functions:
            if func in functions:
                print(f"✅ Função '{func}' definida")
            else:
                print(f"❌ Função '{func}' NÃO encontrada")
        
        print("\nTotal de imports verificados")
        print("✅ Estrutura do aplicativo bot está correta")
        
        return all(f in functions for f in expected_functions)
    except Exception as e:
        print(f"❌ Erro ao analisar estrutura: {e}")
        return False


def test_logging_config():
    """Testa se o logging está configurado"""
    print("\n" + "="*80)
    print("🧪 TESTE 6: Validar Configuração de Logging")
    print("="*80)
    
    try:
        import logging
        
        # Cria um logger de teste
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        
        # Testa logging
        logger.info("✅ Sistema de logging funcionando")
        
        return True
    except Exception as e:
        print(f"❌ Erro ao testar logging: {e}")
        return False


def main():
    """Executa todos os testes"""
    print("\n" + "="*80)
    print("🤖 BOT DE MONITORAMENTO - SUITE DE TESTES")
    print("="*80)
    
    tests = [
        ("Imports", test_imports),
        ("Arquivo .env", test_env_file),
        ("Estrutura de Diretórios", test_directory_structure),
        ("Sintaxe do bot.py", test_bot_syntax),
        ("Estrutura do bot.py", test_code_structure),
        ("Configuração de Logging", test_logging_config),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Exceção não tratada no teste '{test_name}': {e}")
            results[test_name] = False
    
    # Resumo dos testes
    print("\n" + "="*80)
    print("📊 RESUMO DOS TESTES")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASSOU" if passed_test else "❌ FALHOU"
        print(f"{status}: {test_name}")
    
    print(f"\nResultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n🎉 TODOS OS TESTES PASSARAM! O bot está pronto para uso.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} teste(s) falharam. Verifique os erros acima.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
