"""Base de conhecimento defensiva interna do JARVIS."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


DEFAULT_SECURITY_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "identity_and_access": {
        "titulo": "Identidade e acesso",
        "foco": "Controlar quem acessa o sistema, como acessa e com qual nivel de privilegio.",
        "ativos_relacionados": ["token", "device_trust", "sessao_painel", "configuracao"],
        "controles": [
            {
                "control_id": "token_management",
                "nome": "Gestao de tokens",
                "descricao": "Garantir token configurado, armazenamento seguro e validacao consistente em endpoints protegidos.",
                "ativos_relacionados": ["token", "api", "configuracao"],
                "sinais_de_risco": [
                    "token padrao em ambiente sensivel",
                    "token ausente",
                    "token exposto em log ou relatorio",
                ],
                "hipoteses_de_falha": [
                    "uso de credencial padrao em producao",
                    "aceitacao indevida de requisicao sem token",
                ],
                "perguntas_de_diagnostico": [
                    "o token de acesso esta configurado por ambiente?",
                    "existe evidência de tentativa negada quando o token falha?",
                ],
            },
            {
                "control_id": "trusted_device_validation",
                "nome": "Validacao de dispositivo confiavel",
                "descricao": "Conferir device id autorizado antes de liberar operacoes sensiveis e acesso ao painel.",
                "ativos_relacionados": ["device_trust", "painel", "api"],
                "sinais_de_risco": [
                    "device id ausente",
                    "device id nao autorizado",
                    "sessao do painel sem lastro no dispositivo confiavel",
                ],
                "hipoteses_de_falha": [
                    "bypass da validacao de dispositivo",
                    "sessao persistente liberada para device divergente",
                ],
                "perguntas_de_diagnostico": [
                    "os endpoints protegidos exigem device id e token?",
                    "tentativas negadas sao rastreadas em auditoria?",
                ],
            },
            {
                "control_id": "session_minimum_scope",
                "nome": "Sessao com escopo minimo",
                "descricao": "Liberar o painel apenas com sessao derivada de token e device confiavel, sem ampliar privilegios.",
                "ativos_relacionados": ["sessao_painel", "painel"],
                "sinais_de_risco": [
                    "sessao sem ligacao com o dispositivo",
                    "sessao mantida apos invalidacao do acesso",
                ],
                "hipoteses_de_falha": [
                    "reuso indevido de sessao web",
                    "persistencia desnecessaria da sessao",
                ],
                "perguntas_de_diagnostico": [
                    "a sessao deriva de token e device id autorizados?",
                    "a limpeza da sessao remove o acesso ao painel?",
                ],
            },
            {
                "control_id": "least_privilege",
                "nome": "Privilegio minimo",
                "descricao": "Reduzir a superficie de impacto permitindo apenas o acesso necessario a cada componente.",
                "ativos_relacionados": ["runtime", "api", "painel", "workers"],
                "sinais_de_risco": [
                    "acao sensivel sem aprovacao humana",
                    "worker executando fora do proprio dominio",
                ],
                "hipoteses_de_falha": [
                    "expansao indevida de permissao",
                    "remocao de barreiras de supervisao",
                ],
                "perguntas_de_diagnostico": [
                    "ha controles de dominio e supervisao antes da execucao?",
                    "o runtime evita escalada silenciosa de privilegios?",
                ],
            },
            {
                "control_id": "access_separation",
                "nome": "Separacao de acesso",
                "descricao": "Diferenciar healthcheck publico, painel autenticado e endpoints protegidos.",
                "ativos_relacionados": ["healthcheck", "api", "painel"],
                "sinais_de_risco": [
                    "endpoint sensivel sem autenticacao",
                    "mistura entre rota publica e rota operacional",
                ],
                "hipoteses_de_falha": [
                    "exposicao indevida de superficie operacional",
                    "vazamento de metadados sensiveis em rota publica",
                ],
                "perguntas_de_diagnostico": [
                    "as rotas publicas expõem apenas o minimo necessario?",
                    "os endpoints operacionais continuam protegidos?",
                ],
            },
        ],
    },
    "application": {
        "titulo": "Aplicacao",
        "foco": "Endurecer a camada HTTP e a validacao interna para evitar exposicao ou comportamento inconsistente.",
        "ativos_relacionados": ["api", "painel", "payloads", "relatorios"],
        "controles": [
            {
                "control_id": "endpoint_protection",
                "nome": "Protecao de endpoints",
                "descricao": "Garantir que endpoints protegidos mantenham o gate de autenticacao e dispositivo confiavel.",
                "ativos_relacionados": ["api", "autenticacao"],
                "sinais_de_risco": [
                    "rota operacional exposta sem dependencia de autenticacao",
                    "rota nova sem padrao de protecao",
                ],
                "hipoteses_de_falha": [
                    "esquecimento de dependencia de seguranca",
                    "retrocesso acidental em rota protegida",
                ],
                "perguntas_de_diagnostico": [
                    "rotas operacionais exigem credenciais validas?",
                    "rotas publicas foram reduzidas ao minimo?",
                ],
            },
            {
                "control_id": "input_validation",
                "nome": "Validacao de entrada",
                "descricao": "Manter contratos claros de payload e saneamento minimo antes de persistir ou executar.",
                "ativos_relacionados": ["fila", "objetivos", "api"],
                "sinais_de_risco": [
                    "payload inconsistente",
                    "campo sensivel ausente ou invalido",
                ],
                "hipoteses_de_falha": [
                    "tarefa malformada quebrando o runtime",
                    "estado persistido com valores incoerentes",
                ],
                "perguntas_de_diagnostico": [
                    "entradas passam por validacao deterministica?",
                    "estados persistidos sao normalizados antes do uso?",
                ],
            },
            {
                "control_id": "data_exposure_control",
                "nome": "Controle de exposicao de dados",
                "descricao": "Evitar vazamento desnecessario de segredos, paths e estado operacional em respostas externas.",
                "ativos_relacionados": ["relatorios", "configuracao", "token"],
                "sinais_de_risco": [
                    "segredo em resposta HTTP",
                    "dados internos sem necessidade na camada publica",
                ],
                "hipoteses_de_falha": [
                    "payload de healthcheck revelando dado sensivel",
                    "log contendo segredo configuracional",
                ],
                "perguntas_de_diagnostico": [
                    "respostas publicas omitem segredos e credenciais?",
                    "campos expostos sao tecnicamente uteis e proporcionais?",
                ],
            },
            {
                "control_id": "secure_configuration",
                "nome": "Configuracao segura",
                "descricao": "Concentrar defaults, validar ambiente e evitar subida insegura em producao.",
                "ativos_relacionados": ["configuracao", "deploy", "api"],
                "sinais_de_risco": [
                    "valor padrao em producao",
                    "porta ou host incoerente",
                    "configuracao critica ausente",
                ],
                "hipoteses_de_falha": [
                    "subida de servico com segredo padrao",
                    "ambiente sensivel com configuracao incompleta",
                ],
                "perguntas_de_diagnostico": [
                    "o ambiente valida segredos e portas antes do startup?",
                    "os paths persistentes sao controlados por configuracao?",
                ],
            },
            {
                "control_id": "secrets_environment_handling",
                "nome": "Segredos e variaveis de ambiente",
                "descricao": "Separar configuracao sensivel do codigo e evitar exposicao indevida em relatórios e logs.",
                "ativos_relacionados": ["token", "device_trust", "configuracao"],
                "sinais_de_risco": [
                    "segredo em arquivo versionado",
                    "variavel critica ausente",
                ],
                "hipoteses_de_falha": [
                    "deploy sem token proprio",
                    "device id sensivel ausente ou incorreto",
                ],
                "perguntas_de_diagnostico": [
                    "segredos estao fora do repositorio e do payload publico?",
                    "a camada de configuracao denuncia defaults inseguros?",
                ],
            },
        ],
    },
    "infrastructure": {
        "titulo": "Infraestrutura",
        "foco": "Fortalecer deploy, processo e persistencia em ambiente simples e barato.",
        "ativos_relacionados": ["docker", "volumes", "logs", "processo", "ports"],
        "controles": [
            {
                "control_id": "host_and_port_binding",
                "nome": "Portas e bind",
                "descricao": "Subir a API com host e porta configuraveis, mantendo a superficie minima necessaria.",
                "ativos_relacionados": ["api", "deploy"],
                "sinais_de_risco": [
                    "porta errada",
                    "bind inconsistente",
                ],
                "hipoteses_de_falha": [
                    "servico inacessivel",
                    "exposicao imprevista por bind inadequado",
                ],
                "perguntas_de_diagnostico": [
                    "host e porta estao coerentes com o ambiente?",
                    "o healthcheck responde na porta esperada?",
                ],
            },
            {
                "control_id": "container_hardening",
                "nome": "Containerizacao segura",
                "descricao": "Usar imagem leve, entrypoint claro e artefatos minimos no container.",
                "ativos_relacionados": ["docker", "deploy"],
                "sinais_de_risco": [
                    "imagem pesada sem necessidade",
                    "comando de startup ambíguo",
                ],
                "hipoteses_de_falha": [
                    "deploy nao reproduzivel",
                    "container sem comportamento previsivel",
                ],
                "perguntas_de_diagnostico": [
                    "o container sobe com um unico comando?",
                    "as dependencias de runtime estao explicitas?",
                ],
            },
            {
                "control_id": "volume_and_persistence",
                "nome": "Volumes e persistencia",
                "descricao": "Preservar fila, memoria e objetivos fora de caminhos efemeros.",
                "ativos_relacionados": ["fila", "memoria", "objetivos", "volumes"],
                "sinais_de_risco": [
                    "dados em caminho efemero",
                    "volume ausente",
                    "persistencia parcial",
                ],
                "hipoteses_de_falha": [
                    "perda de estado apos reinicio",
                    "recuperacao incompleta de memoria e fila",
                ],
                "perguntas_de_diagnostico": [
                    "os paths persistentes estao configurados e montados?",
                    "fila, memoria e objetivos sobrevivem ao restart?",
                ],
            },
            {
                "control_id": "log_storage",
                "nome": "Armazenamento de logs",
                "descricao": "Manter logs locais, legiveis e separados dos dados de negocio.",
                "ativos_relacionados": ["logs", "observabilidade"],
                "sinais_de_risco": [
                    "log ausente",
                    "log misturado com segredos",
                ],
                "hipoteses_de_falha": [
                    "incapacidade de reconstruir startup e shutdown",
                    "auditoria empobrecida",
                ],
                "perguntas_de_diagnostico": [
                    "o servidor grava logs em path previsivel?",
                    "startup e shutdown deixam rastros claros?",
                ],
            },
            {
                "control_id": "process_supervision",
                "nome": "Supervisao do processo",
                "descricao": "Subir API e loop com estrategia simples, rastreavel e controlada.",
                "ativos_relacionados": ["runtime", "server", "loop"],
                "sinais_de_risco": [
                    "loop sem controle de inicio e parada",
                    "processo sem fechamento limpo",
                ],
                "hipoteses_de_falha": [
                    "estado nao persistido no encerramento",
                    "reinicio sem resumo de ambiente",
                ],
                "perguntas_de_diagnostico": [
                    "o processo registra startup, loop e shutdown?",
                    "o loop pode ser desligado por configuracao?",
                ],
            },
        ],
    },
    "continuity": {
        "titulo": "Continuidade",
        "foco": "Preservar estado, tolerar falhas e garantir retomada segura.",
        "ativos_relacionados": ["fila", "memoria", "objetivos", "runtime", "reports"],
        "controles": [
            {
                "control_id": "backup_and_recovery",
                "nome": "Backup e recuperacao",
                "descricao": "Gerar copia de seguranca quando um armazenamento critico estiver corrompido.",
                "ativos_relacionados": ["fila", "memoria", "objetivos"],
                "sinais_de_risco": [
                    "JSON corrompido",
                    "recuperacao sem preservacao do arquivo anterior",
                ],
                "hipoteses_de_falha": [
                    "perda irreversivel de snapshot",
                    "boot quebrado por arquivo invalido",
                ],
                "perguntas_de_diagnostico": [
                    "o bootstrap cria backup antes de reinicializar um arquivo corrompido?",
                    "a recuperacao fica registrada em log?",
                ],
            },
            {
                "control_id": "safe_restart",
                "nome": "Restart seguro",
                "descricao": "Permitir reinicio sem perder contexto operacional essencial.",
                "ativos_relacionados": ["runtime", "fila", "memoria"],
                "sinais_de_risco": [
                    "retomada com estado parcial",
                    "runtime sem planner acoplado apos restart",
                ],
                "hipoteses_de_falha": [
                    "reinicio inconsistente",
                    "queue depth divergente apos retomada",
                ],
                "perguntas_de_diagnostico": [
                    "o runtime recupera fila, memoria e objetivos no startup?",
                    "o relatorio de shutdown ajuda a explicar a retomada seguinte?",
                ],
            },
            {
                "control_id": "fault_tolerance",
                "nome": "Tolerancia a falhas",
                "descricao": "Reduzir impacto de falhas esperadas e impedir degradacao silenciosa.",
                "ativos_relacionados": ["server", "runtime", "persistencia"],
                "sinais_de_risco": [
                    "erro sem registro",
                    "estado degradado sem sinalizacao",
                ],
                "hipoteses_de_falha": [
                    "degradacao silenciosa de persistencia",
                    "falha recorrente do loop sem visibilidade",
                ],
                "perguntas_de_diagnostico": [
                    "falhas esperadas geram logs e relatorios claros?",
                    "o sistema prefere degradacao segura a corrupcao silenciosa?",
                ],
            },
            {
                "control_id": "safe_degradation",
                "nome": "Degradacao segura",
                "descricao": "Manter o minimo operacional quando um componente nao puder subir integralmente.",
                "ativos_relacionados": ["healthcheck", "api", "runtime"],
                "sinais_de_risco": [
                    "queda total por falta de dado nao critico",
                    "estado de saude inconsistente",
                ],
                "hipoteses_de_falha": [
                    "colapso do servico por dependencia parcial",
                    "healthcheck reportando normalidade falsa",
                ],
                "perguntas_de_diagnostico": [
                    "o healthcheck denuncia configuracao degradada?",
                    "a API continua reportando estado ao inves de falhar em silencio?",
                ],
            },
        ],
    },
    "observability": {
        "titulo": "Observabilidade",
        "foco": "Tornar falhas, decisoes e mudancas rastreaveis para diagnostico e governanca.",
        "ativos_relacionados": ["logs", "audit_logger", "healthcheck", "reports"],
        "controles": [
            {
                "control_id": "log_quality",
                "nome": "Qualidade de logs",
                "descricao": "Manter mensagens legiveis, com contexto suficiente para startup, loop e shutdown.",
                "ativos_relacionados": ["logs", "server"],
                "sinais_de_risco": [
                    "logs insuficientes",
                    "logs sem contexto de evento",
                ],
                "hipoteses_de_falha": [
                    "dificuldade de diagnostico operacional",
                    "impossibilidade de explicar retomada ou falha",
                ],
                "perguntas_de_diagnostico": [
                    "startup e shutdown geram mensagens claras?",
                    "o loop deixa rastro suficiente para investigar falhas?",
                ],
            },
            {
                "control_id": "healthcheck_consistency",
                "nome": "Consistencia do healthcheck",
                "descricao": "Refletir o estado real de API, runtime, planner, memoria, fila e configuracao.",
                "ativos_relacionados": ["healthcheck", "runtime", "api"],
                "sinais_de_risco": [
                    "healthcheck verde com estado degradado",
                    "campos de saude incompletos",
                ],
                "hipoteses_de_falha": [
                    "falso positivo de disponibilidade",
                    "falso negativo de configuracao critica",
                ],
                "perguntas_de_diagnostico": [
                    "o healthcheck cobre autenticacao, fila, memoria e objetivos?",
                    "ha separacao entre saude publica e diagnostico protegido?",
                ],
            },
            {
                "control_id": "audit_integrity",
                "nome": "Integridade de auditoria",
                "descricao": "Preservar rastreabilidade de decisoes do planner, acessos e eventos relevantes.",
                "ativos_relacionados": ["audit_logger", "runtime", "api"],
                "sinais_de_risco": [
                    "evento sensivel sem auditoria",
                    "tentativa negada sem rastro",
                ],
                "hipoteses_de_falha": [
                    "perda de rastreabilidade de acesso",
                    "investigacao prejudicada por lacuna de auditoria",
                ],
                "perguntas_de_diagnostico": [
                    "decisoes do planner sao auditadas?",
                    "acessos negados aparecem em auditoria e memoria episodica?",
                ],
            },
            {
                "control_id": "traceability_chain",
                "nome": "Cadeia de rastreabilidade",
                "descricao": "Conectar configuracao, startup, runtime, relatorios e persistencia em uma trilha coerente.",
                "ativos_relacionados": ["reports", "logs", "runtime", "configuracao"],
                "sinais_de_risco": [
                    "relatorio sem origem",
                    "log sem contexto do ambiente",
                ],
                "hipoteses_de_falha": [
                    "mudanca sem explicacao de antes e depois",
                    "baixa capacidade de governanca sobre o sistema",
                ],
                "perguntas_de_diagnostico": [
                    "relatorios de ambiente e shutdown refletem o estado real?",
                    "e possivel explicar uma mudanca relevante sem ambiguidade?",
                ],
            },
        ],
    },
}


@dataclass
class SecurityKnowledgeCore:
    """Mantem uma base defensiva reutilizavel para diagnostico e modelagem de risco."""

    version: str = "0.1.0"
    locale: str = "pt-BR"
    knowledge_map: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: deepcopy(DEFAULT_SECURITY_KNOWLEDGE)
    )

    def list_domains(self) -> List[Dict[str, Any]]:
        """Lista os dominios defensivos com metadados resumidos."""

        domains: List[Dict[str, Any]] = []
        for domain_id, domain in self.knowledge_map.items():
            domains.append(
                {
                    "domain_id": domain_id,
                    "titulo": domain["titulo"],
                    "foco": domain["foco"],
                    "ativos_relacionados": list(domain["ativos_relacionados"]),
                    "total_controles": len(domain["controles"]),
                }
            )
        return domains

    def get_domain(self, domain_id: str) -> Dict[str, Any]:
        """Retorna um dominio defensivo completo."""

        if domain_id not in self.knowledge_map:
            raise KeyError(f"Dominio defensivo nao encontrado: {domain_id}")
        domain = deepcopy(self.knowledge_map[domain_id])
        domain["domain_id"] = domain_id
        return domain

    def get_control(self, control_id: str) -> Dict[str, Any]:
        """Recupera um controle especifico por identificador."""

        for domain_id, domain in self.knowledge_map.items():
            for control in domain["controles"]:
                if control["control_id"] == control_id:
                    payload = deepcopy(control)
                    payload["domain_id"] = domain_id
                    payload["domain_title"] = domain["titulo"]
                    return payload
        raise KeyError(f"Controle defensivo nao encontrado: {control_id}")

    def iter_controls(self) -> Iterable[Dict[str, Any]]:
        """Itera sobre todos os controles defensivos conhecidos."""

        for domain_id, domain in self.knowledge_map.items():
            for control in domain["controles"]:
                payload = deepcopy(control)
                payload["domain_id"] = domain_id
                payload["domain_title"] = domain["titulo"]
                yield payload

    def build_knowledge_snapshot(self) -> Dict[str, Any]:
        """Retorna um snapshot resumido do nucleo defensivo."""

        controls = list(self.iter_controls())
        return {
            "version": self.version,
            "locale": self.locale,
            "total_dominios": len(self.knowledge_map),
            "total_controles": len(controls),
            "dominios": self.list_domains(),
            "controle_ids": [control["control_id"] for control in controls],
        }

    def build_semantic_seed_entries(self) -> List[Dict[str, Any]]:
        """Gera entradas prontas para memoria semantica."""

        entries: List[Dict[str, Any]] = []
        for control in self.iter_controls():
            entries.append(
                {
                    "content": "{nome}: {descricao}".format(
                        nome=control["nome"],
                        descricao=control["descricao"],
                    ),
                    "domain": "security",
                    "tags": [
                        "seguranca",
                        "autodefesa",
                        control["domain_id"],
                        control["control_id"],
                    ],
                    "source": "security.security_knowledge_core",
                    "importance": 4,
                    "metadata": {
                        "domain_id": control["domain_id"],
                        "domain_title": control["domain_title"],
                        "control_id": control["control_id"],
                        "ativos_relacionados": list(control["ativos_relacionados"]),
                        "sinais_de_risco": list(control["sinais_de_risco"]),
                    },
                }
            )
        return entries

    def build_procedural_guides(self) -> List[Dict[str, Any]]:
        """Gera guias procedurais reutilizaveis para diagnostico defensivo."""

        guides: List[Dict[str, Any]] = []
        for domain_id, domain in self.knowledge_map.items():
            steps = [
                "inventariar ativos e controles relacionados",
                "revisar sinais de risco observados",
                "comparar hipoteses de falha com o estado atual",
                "registrar evidencias auditaveis",
                "escalar apenas o que exigir aprovacao humana",
            ]
            guides.append(
                {
                    "procedure_id": f"security_review_{domain_id}",
                    "titulo": f"Revisao defensiva de {domain['titulo'].lower()}",
                    "domain_id": domain_id,
                    "steps": steps,
                }
            )
        return guides

    def seed_memories(self, semantic_memory: Any, procedural_memory: Any) -> Dict[str, int]:
        """Semeia conhecimento defensivo em memorias compativeis do sistema."""

        semantic_entries = self.build_semantic_seed_entries()
        procedural_guides = self.build_procedural_guides()

        for entry in semantic_entries:
            semantic_memory.add_entry(**entry)

        for guide in procedural_guides:
            procedural_memory.register(guide["procedure_id"], guide["steps"])

        return {
            "semantic_entries_added": len(semantic_entries),
            "procedural_guides_added": len(procedural_guides),
        }

    def build_defensive_summary(self) -> Dict[str, Any]:
        """Resume a base defensiva em formato legivel para a camada visivel."""

        snapshot = self.build_knowledge_snapshot()
        return {
            "mensagem": "Nucleo de conhecimento defensivo carregado.",
            "versao": snapshot["version"],
            "idioma": snapshot["locale"],
            "dominios": snapshot["dominios"],
            "total_controles": snapshot["total_controles"],
        }
