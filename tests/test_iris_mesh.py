"""Malha Iris: pareamento autorizado, adaptação declarativa e sobrevivencia parcial."""
from __future__ import annotations

import secrets
import unittest

from device.iris_mesh import IrisDeviceMesh
from security.iris_instance_policy import IrisInstanceAuthority


class IrisMeshTests(unittest.TestCase):
    def setUp(self):
        self.now = 2_000_000_000.0
        self.secret = secrets.token_urlsafe(32)
        self.identity = IrisInstanceAuthority(self.secret, clock=lambda: self.now)
        self.mesh = IrisDeviceMesh(self.identity, clock=lambda: self.now)
        self.owner_id = IrisInstanceAuthority.OWNER_ID

    def pair(self, instance_id=None, token=None, *, name="PC", kind="windows",
             surfaces=None, mode="integrated", visit_seconds=1800):
        instance_id = instance_id or self.owner_id
        token = token or self.secret
        offer = self.mesh.offer_device(
            device_name=name, device_type=kind,
            surfaces=surfaces or {"presence.display", "compute.light"},
            locally_approved=True, mode=mode,
        )
        return self.mesh.approve_offer(
            instance_id, token, offer_id=offer["offer_id"],
            verification_code=offer["verification_code"], visit_seconds=visit_seconds,
        )

    def test_windows_mobile_and_switch_share_one_logical_iris(self):
        pc = self.pair(name="desktop", kind="windows")
        phone = self.pair(name="android", kind="android", surfaces={"compute.light", "audio.output"})
        switch = self.pair(name="switch", kind="switch", surfaces={"diagnostics.read"})
        nodes = self.mesh.devices(self.owner_id, self.secret)
        self.assertEqual(len(nodes), 3)
        self.assertEqual(
            {node["execution_kind"] for node in nodes},
            {"native_agent", "gateway_adapter"},
        )
        self.assertEqual(
            self.mesh.route(self.owner_id, self.secret, surface="audio.output")["node_id"],
            phone["node_id"],
        )
        self.assertFalse(self.mesh.route(self.owner_id, self.secret, surface="audio.output")["executed"])
        self.assertEqual(
            self.mesh.route(self.owner_id, self.secret, surface="diagnostics.read")["node_id"],
            switch["node_id"],
        )
        state = self.mesh.continuity(self.owner_id, self.secret)
        self.assertEqual(state["logical_instance_id"], self.owner_id)
        self.assertEqual(state["active_nodes"], 3)
        self.assertEqual(state["alternate_nodes"], 1)
        self.assertFalse(state["durable_state_replication"])

    def test_modo_visita_expira_e_nao_vira_coordenador(self):
        visitor = self.pair(mode="visit", visit_seconds=60)
        self.assertIsNone(self.mesh.continuity(self.owner_id, self.secret)["coordinator_candidate"])
        self.assertEqual(self.mesh.continuity(self.owner_id, self.secret)["active_nodes"], 1)
        self.now += 61
        self.assertEqual(self.mesh.devices(self.owner_id, self.secret), [])
        self.assertEqual(self.mesh.continuity(self.owner_id, self.secret)["active_nodes"], 0)
        with self.assertRaises(PermissionError):
            self.mesh.heartbeat(visitor["node_id"], visitor["node_token"])

    def test_no_desligado_outro_assume_presenca_sem_promessa_de_memoria(self):
        pc = self.pair(kind="windows", name="PC")
        mobile = self.pair(kind="android", name="celular", surfaces={"compute.light"})
        self.now += 100
        self.mesh.heartbeat(mobile["node_id"], mobile["node_token"])
        health = self.mesh.continuity(self.owner_id, self.secret)
        self.assertEqual(health["active_nodes"], 1)
        self.assertEqual(health["coordinator_candidate"], mobile["node_id"])
        self.assertFalse(health["guaranteed_failover"])
        self.assertFalse(health["durable_state_replication"])
        self.now += 100
        state = self.mesh.continuity(self.owner_id, self.secret)
        self.assertEqual(state["active_nodes"], 0)
        self.assertFalse(state["control_plane_running"])
        self.assertNotEqual(pc["node_id"], mobile["node_id"])

    def test_pareamento_exige_consentimento_local_e_codigo_uma_vez(self):
        with self.assertRaises(PermissionError):
            self.mesh.offer_device(
                device_name="PC estranho", device_type="windows",
                surfaces={"compute.light"}, locally_approved=False,
            )
        offer = self.mesh.offer_device(
            device_name="PC", device_type="windows",
            surfaces={"compute.light"}, locally_approved=True,
        )
        with self.assertRaises(PermissionError):
            self.mesh.approve_offer(
                self.owner_id, self.secret, offer_id=offer["offer_id"],
                verification_code="codigo-errado",
            )
        with self.assertRaises(PermissionError):
            self.mesh.approve_offer(
                self.owner_id, self.secret, offer_id=offer["offer_id"],
                verification_code=offer["verification_code"],
            )

    def test_codigo_expira_sem_conexao(self):
        offer = self.mesh.offer_device(
            device_name="celular", device_type="android",
            surfaces={"audio.output"}, locally_approved=True,
        )
        self.now += 301
        with self.assertRaises(PermissionError):
            self.mesh.approve_offer(
                self.owner_id, self.secret, offer_id=offer["offer_id"],
                verification_code=offer["verification_code"],
            )

    def test_nao_instala_programa_em_switch_ou_patinetes(self):
        for kind in ("router", "switch", "scooter", "coffee_machine"):
            with self.subTest(kind=kind):
                with self.assertRaises(PermissionError):
                    self.mesh.offer_device(
                        device_name="dispositivo", device_type=kind,
                        surfaces={"automation.authorized"}, locally_approved=True,
                    )
                adapter = self.pair(
                    kind=kind, name=kind, surfaces={"diagnostics.read"},
                )
                node = next(
                    d for d in self.mesh.devices(self.owner_id, self.secret)
                    if d["node_id"] == adapter["node_id"]
                )
                self.assertEqual(node["execution_kind"], "gateway_adapter")

    def test_tela_smart_tv_nao_ganha_captura_microfone(self):
        with self.assertRaises(PermissionError):
            self.mesh.offer_device(
                device_name="TV", device_type="smart_tv",
                surfaces={"audio.input"}, locally_approved=True,
            )
        device = self.pair(kind="smart_tv", name="TV", surfaces={"presence.display"})
        self.assertEqual(
            self.mesh.route(self.owner_id, self.secret, surface="presence.display")["node_id"],
            device["node_id"],
        )

    def test_dispositivos_ficam_isolados_por_instancia(self):
        alice = self.identity.create_resident(
            self.secret, tenant_id="cliente-alice",
            display_name="Iris Alice", user_consented=True,
        )
        bob = self.identity.create_resident(
            self.secret, tenant_id="cliente-bob",
            display_name="Iris Bob", user_consented=True,
        )
        a = self.pair(alice["instance_id"], alice["token"], name="A")
        b = self.pair(bob["instance_id"], bob["token"], name="B")
        self.assertEqual(
            [d["node_id"] for d in self.mesh.devices(alice["instance_id"], alice["token"])],
            [a["node_id"]],
        )
        self.assertEqual(
            [d["node_id"] for d in self.mesh.devices(bob["instance_id"], bob["token"])],
            [b["node_id"]],
        )
        with self.assertRaises(PermissionError):
            self.mesh.disconnect(alice["instance_id"], alice["token"], node_id=b["node_id"])
        with self.assertRaises(PermissionError):
            self.mesh.heartbeat(a["node_id"], b["node_token"])

    def test_deletar_no_revoga_token_mas_arquivos_dependem_do_cliente(self):
        node = self.pair()
        result = self.mesh.disconnect(self.owner_id, self.secret, node_id=node["node_id"])
        self.assertTrue(result["local_cleanup_required"])
        self.assertTrue(result["disconnected"])
        with self.assertRaises(PermissionError):
            self.mesh.heartbeat(node["node_id"], node["node_token"])
        self.assertEqual(self.mesh.devices(self.owner_id, self.secret), [])

    def test_revogacao_da_residente_interrompe_todos_os_nos(self):
        resident = self.identity.create_resident(
            self.secret, tenant_id="cliente-001",
            display_name="Iris cliente", user_consented=True,
        )
        node = self.pair(resident["instance_id"], resident["token"])
        self.identity.revoke(self.owner_id, self.secret, resident["instance_id"])
        with self.assertRaises(PermissionError):
            self.mesh.heartbeat(node["node_id"], node["node_token"])
        with self.assertRaises(PermissionError):
            self.mesh.devices(resident["instance_id"], resident["token"])

    def test_no_nao_executa_comando_somente_retorna_plano(self):
        self.assertEqual(
            self.mesh.route(self.owner_id, self.secret, surface="compute.infer")["status"],
            "unavailable",
        )
        with self.assertRaises(ValueError):
            self.mesh.route(self.owner_id, self.secret, surface="device.hack")

    def test_perfil_aprende_capacidade_sem_dados_pessoais(self):
        pc = self.pair(name="desktop", kind="windows")
        tablet = self.pair(name="tablet", kind="android")
        self.mesh.report_health(
            pc["node_id"], pc["node_token"],
            cpu_percent=99.0, memory_available_mb=1024,
            battery_percent=None, latency_ms=12,
        )
        self.mesh.report_health(
            tablet["node_id"], tablet["node_token"],
            cpu_percent=10.0, memory_available_mb=4096,
            battery_percent=80.0, latency_ms=25,
        )
        route = self.mesh.route(
            self.owner_id, self.secret, surface="compute.light",
        )
        self.assertEqual(route["node_id"], tablet["node_id"])
        profiles = self.mesh.resource_profiles(self.owner_id, self.secret)
        self.assertEqual(len(profiles), 2)
        self.assertFalse(any("conversation" in str(profile) for profile in profiles))
        for profile in profiles:
            self.assertNotIn("token", profile)
        self.mesh.report_health(
            tablet["node_id"], tablet["node_token"],
            cpu_percent=20.0, memory_available_mb=4096,
            battery_percent=75.0, latency_ms=15,
        )
        update = next(profile for profile in
                      self.mesh.resource_profiles(self.owner_id, self.secret)
                      if profile["node_id"] == tablet["node_id"])
        self.assertEqual(update["samples"], 2)
        self.assertEqual(update["cpu_percent"], 13.0)

    def test_bateria_e_memoria_baixas_suspendem_roteamento_pesado(self):
        laptop = self.pair(name="laptop", kind="linux")
        self.mesh.report_health(
            laptop["node_id"], laptop["node_token"],
            cpu_percent=10.0, memory_available_mb=64,
            battery_percent=2.0, latency_ms=20.0,
        )
        self.assertEqual(
            self.mesh.route(self.owner_id, self.secret,
                            surface="compute.light")["status"],
            "unavailable",
        )
        # Presenca visual continua permitida, se suportada.
        self.assertEqual(
            self.mesh.route(self.owner_id, self.secret,
                            surface="presence.display")["status"],
            "routed",
        )

    def test_perfil_rejeita_telemetria_invalida(self):
        laptop = self.pair()
        for invalid in (float("nan"), float("inf"), True, -1, 101):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.mesh.report_health(
                        laptop["node_id"], laptop["node_token"],
                        cpu_percent=invalid, memory_available_mb=1000,
                        battery_percent=None, latency_ms=10,
                    )
        with self.assertRaises(ValueError):
            self.mesh.report_health(
                laptop["node_id"], laptop["node_token"],
                cpu_percent=1, memory_available_mb=1000,
                battery_percent=None, latency_ms=float("nan"),
            )

    def test_perfis_nao_vazam_entre_residentes(self):
        resident = self.identity.create_resident(
            self.secret, tenant_id="cliente-001",
            display_name="Iris local", user_consented=True,
        )
        node = self.pair(resident["instance_id"], resident["token"])
        self.mesh.report_health(
            node["node_id"], node["node_token"], cpu_percent=20,
            memory_available_mb=1024, battery_percent=90, latency_ms=10,
        )
        self.assertEqual(self.mesh.resource_profiles(self.owner_id, self.secret), [])
        self.assertEqual(
            len(self.mesh.resource_profiles(resident["instance_id"], resident["token"])),
            1,
        )

    def test_credencial_da_iris_nao_basta_para_forjar_heartbeat(self):
        node = self.pair()
        with self.assertRaises(PermissionError):
            self.mesh.heartbeat(node["node_id"], self.secret)
        self.mesh.heartbeat(node["node_id"], node["node_token"])


if __name__ == "__main__":
    unittest.main()
