# Guia de Continuidade de Desenvolvimento

## Projeto

- Nome do projeto: Sistema Cognitivo JARVIS
- Versao da arquitetura: 0.1.0
- Raiz do projeto: `jarvis_core/`
- Entrypoint do runtime: `jarvis_core/runtime/internal_agent_runtime.py`
- Idioma padrao: `pt-BR`

## Modulos

- `constitutional_core`
- `executive_planner`
- `intent_layer`
- `memory_system`
- `workers`
- `runtime`
- `infrastructure`
- `interface`
- `tests`

## Proximo Modulo Recomendado

Proxima tarefa sugerida:

- consolidar a camada de interface para expor o runtime em pt-BR sem alterar os identificadores internos estaveis do codigo

## Retomar Desenvolvimento no VS Code

1. Abra um terminal na workspace do projeto.
2. Entre no repositorio:
   - `cd jarvis_core`
3. Abra o projeto no VS Code:
   - `code .`
4. Revise primeiro:
   - `README.md`
   - `ARCHITECTURE.md`
   - `runtime/internal_agent_runtime.py`
   - `executive_planner/planner.py`
   - `memory_system/semantic_memory.py`
5. Confirme que o repositorio esta limpo antes de iniciar novas alteracoes:
   - `git status`
6. Continue a partir da proxima tarefa e adicione testes em `tests/` sempre que houver nova integracao visivel ao usuario.

## ABRIR NO VSCODE

```powershell
cd jarvis_core
code .
```

## Confirmacao do Entrypoint

- Entrypoint do runtime: `jarvis_core/runtime/internal_agent_runtime.py`
