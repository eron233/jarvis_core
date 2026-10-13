# JARVIS Capability Foundry + REA (primeiro bloco experimental)

**Branch:** `dev` • **Estado:** prototipo funcional de uma capacidade, não uma fábrica autônoma completa.

## Objetivo

O JARVIS pode reutilizar software livre e acrescentar interfaces próprias,
sem copiar codigo proprietario ou contornar assinaturas/conteudo protegido.
A engenharia reversa autorizada entra como ferramenta de investigação,
não como meio de recuperar licenças, bibliotecas comerciais ou direitos.

## 1. REA como provedor MCP opcional

Fonte: https://github.com/morluto/rea • REA 6.4.0 (data de referência: 13-10-2026).

- O exemplo `config/mcp_servers.example.json` possui servidor `rea-investigation`
  **desabilitado**, com transporte `stdio`.
- O launcher usa `node` com entrada local `scripts/rea.mjs mcp`, e **nunca
  `npx -y` nem instalação/atualização automática**.
- As únicas ferramentas listadas como permissões iniciais são
  `inspect_managed_artifact`, `inspect_managed_members`,
  `analyze_javascript_application`, `inspect_analysis_view` e
  `get_evidence_bundle`. Não há permissão de execução, debugging,
  injeção, escrita no alvo ou manipulação de dispositivo.
- O `REAInvestigator` admite apenas análise estática de arquivos .NET
  (PE-CLI) ou JavaScript/Electron e somente no diretório
  `data/rea_targets/`; recusa caminhos externos e alvo symlink.
- API protegida: `POST /api/rea/inspecionar` com
  `{"caminho":"app.dll","tipo":"managed"}` ou
  `{"caminho":"app","tipo":"javascript"}`.
- O retorno é sempre tratado como **dados não confiáveis do programa-alvo**.
  Não transforma pseudocódigo em comandos nem registra descoberta validada
  automaticamente. Uma resposta MCP é evidência a analisar, não prova de
  segurança, correção ou licença.
- **Limite importante:** o MCP manager cria conexão nova a cada chamada.
  Não há uma sessão REA persistente entre chamadas nem ledger local de
  evidências REA; `Evidence Bundle` não deve ser prometido entre sessões.
- No Windows e em outras plataformas, motores externos podem demandar
  Node.js, Ghidra/Java ou outros programas preinstalados. O REA não é sandbox
  e só deve examinar artefatos autorizados; executáveis suspeitos não devem
  ser rodados no host. Uma VM é exigida para investigação dinâmica de malware.

### Ativação manual futura (sem autoinstalação)

1. Instalar Node.js suportado e `rea-agents@6.4.0` por decisão do operador,
   usando pacote de origem confiável; não executar `rea setup` automaticamente.
2. Localizar o `scripts/rea.mjs` efetivamente instalado e substituir o
   placeholder do registro MCP por caminho absoluto local.
3. Copiar apenas a entrada `rea-investigation` ao registro ativo
   `data/mcp_servers.json`; verificar a origem e permissões.
4. Habilitar explicitamente `JARVIS_MCP_ENABLED=true` e incluir `node`
   (ou `node.exe`) na allowlist de executáveis stdio do JARVIS.
5. Alterar apenas `enabled` do servidor REA para `true`, revisar permissões
   e primeiro chamar o endpoint `discover`. Nenhum teste neste bloco prova
   que o REA está instalado e executado no computador do proprietário.

A ampliação de ferramentas exige revisão individual do contrato de
efeitos da ferramenta REA. Annotations MCP não são autorização.

## 2. Foundry v0 (capacidade concreta: video.trim)

Arquivo `runtime/capability_foundry.py`. API protegida:

- `GET /api/foundry/capacidades`: cataloga receitas já disponíveis e a
  disponibilidade de dependências locais.
- `POST /api/foundry/planejar`:
  `{"pedido":"cortar um video","capacidade":"video.trim"}`.
  Não gera código nem executa nada; o estado depende da presença do FFmpeg.
- `POST /api/foundry/video/cortar`:
  `{"arquivo_origem":"entrada.mp4","arquivo_saida":"cortado.mp4",` +
  `"inicio_segundos":1.0,"duracao_segundos":3.0,"aprovado":true}`.
  Sem `aprovado` não executa.

Workspace fixo: `data/studio_media/`. O operador coloca nele o arquivo de
entrada. Apenas arquivos `.mp4` de nome simples são aceitos; nomes de pasta,
path traversal, links no arquivo de entrada e sobregravação são recusados.

A ferramenta invoca `ffmpeg` previamente instalado, sem shell, sem instalar
dependências e com timeout. Gera `.mp4` H.264/AAC; publicação é atômica,
sem sobrescrever destino existente. `arquivo_criado_nao_homologado` não
significa que a mídia foi assistida/reproduzida ou que sua qualidade foi validada.

**Limites:** FFmpeg aqui é uma ferramenta externa do host e ainda não roda
num sandbox forte. Não processar arquivos adversariais sem Tier 3. A primeira
versão não oferece timeline gráfica, edição de áudio sofisticada, codificação
4K comprovada nem criação autônoma de novos módulos.

## 3. Testes e próximas etapas

- `tests/test_capability_foundry.py`: erros, tempos, path traversal,
  autorização, não sobreposição, API e smoke condicionado a FFmpeg local.
- `tests/test_rea_integration.py`: rotas autenticadas, isolamento do
  workspace, modos estáticos e ausência de permissões perigosas.
- O teste de FFmpeg é ignorado se o binário não estiver instalado no runner.
  Aprovação da suíte Python não prova REA/Ghidra instalado ou navegador integrado.
- Próxima etapa: comprovar REA real via MCP e FFmpeg real em runners adequados;
  implementar catálogo de dependências e licenças, blueprint de ferramentas,
  projetos gerados sob controle de versão, testes por requisitos e promoção
  somente após aprovação.

