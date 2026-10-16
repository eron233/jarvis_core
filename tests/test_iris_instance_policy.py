"""Regressoes da politica de instancias Iris: isolamento e privacidade."""
from __future__ import annotations

import secrets
import unittest

from security.iris_instance_policy import IrisInstanceAuthority


class IrisInstancePolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_900_000_000.0
        self.owner_secret = secrets.token_urlsafe(32)
        self.auth = IrisInstanceAuthority(self.owner_secret, clock=lambda: self.now)

    def resident(self, tenant: str = "cliente-001"):
        return self.auth.create_resident(
            self.owner_secret, tenant_id=tenant,
            display_name="Iris do cliente", user_consented=True,
        )

    def test_exclusividade_original_para_dispositivos_e_replicacao(self):
        resident = self.resident()
        owner = self.auth.OWNER_ID
        self.assertTrue(self.auth.require(owner, self.owner_secret, "device.local"))
        self.assertIn("device.local", self.auth.capabilities(owner, self.owner_secret))
        self.assertNotIn("device.local", self.auth.capabilities(
            resident["instance_id"], resident["token"],
        ))
        with self.assertRaises(PermissionError):
            self.auth.require(resident["instance_id"], resident["token"], "device.local")
        with self.assertRaises(PermissionError):
            self.auth.delegate(
                resident["instance_id"], resident["token"],
                capabilities={"device.local"},
            )
        with self.assertRaises(PermissionError):
            self.auth.delegate(
                owner, self.owner_secret, capabilities={"device.local"},
            )
        self.assertTrue(self.auth.require(
            resident["instance_id"], resident["token"], "chat.use",
        ))
        self.assertTrue(self.auth.require(
            resident["instance_id"], resident["token"], "memory.own",
        ))

    def test_senha_curta_nao_habilita_dono(self):
        with self.assertRaises(ValueError):
            IrisInstanceAuthority("admin")

    def test_residente_necessita_consentimento(self):
        with self.assertRaises(PermissionError):
            self.auth.create_resident(
                self.owner_secret, tenant_id="cliente-001",
                display_name="Iris", user_consented=False,
            )

    def test_somente_original_possui_trade_admin_e_corredor(self):
        resident = self.resident()
        for capability in ("trade.use", "system.admin", "corridor.list", "instances.provision"):
            self.assertTrue(
                self.auth.require(IrisInstanceAuthority.OWNER_ID, self.owner_secret, capability)
            )
            self.assertNotIn(capability, self.auth.capabilities(resident["instance_id"], resident["token"]))
            with self.assertRaises(PermissionError):
                self.auth.require(resident["instance_id"], resident["token"], capability)

    def test_token_nao_e_intercambiavel_entre_residentes(self):
        alice = self.resident("cliente-alice")
        bob = self.resident("cliente-bob")
        with self.assertRaises(PermissionError):
            self.auth.room(alice["instance_id"], bob["token"])
        with self.assertRaises(PermissionError):
            self.auth.room(bob["instance_id"], alice["token"])
        with self.assertRaises(PermissionError):
            self.auth.require(
                alice["instance_id"], alice["token"], "memory.own",
                target_instance_id=bob["instance_id"],
            )
        self.assertEqual(
            self.auth.room(bob["instance_id"], bob["token"])["instance_id"],
            bob["instance_id"],
        )

    def test_residente_nao_enxerga_corredor(self):
        alice = self.resident("cliente-alice")
        self.assertEqual(self.auth.corridor(self.owner_secret), [])
        self.auth.set_resident_preferences(
            alice["instance_id"], alice["token"], corridor_visible=True,
        )
        rooms = self.auth.corridor(self.owner_secret)
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["instance_id"], alice["instance_id"])
        self.assertNotIn("token", rooms[0])
        self.assertNotIn("memory", rooms[0])
        with self.assertRaises(PermissionError):
            self.auth.corridor(alice["token"])

    def test_delegada_herda_apenas_subconjunto(self):
        alice = self.resident()
        worker = self.auth.delegate(
            alice["instance_id"], alice["token"],
            capabilities={"chat.use", "diagnostics.local"}, ttl_seconds=300,
        )
        self.assertEqual(
            self.auth.capabilities(worker["instance_id"], worker["token"]),
            ["chat.use", "diagnostics.local"],
        )
        with self.assertRaises(PermissionError):
            self.auth.require(worker["instance_id"], worker["token"], "memory.own")
        with self.assertRaises(PermissionError):
            self.auth.delegate(
                IrisInstanceAuthority.OWNER_ID, self.owner_secret,
                capabilities={"trade.use"},
            )

    def test_delegada_expira_e_cai_apos_revogacao_da_residente(self):
        alice = self.resident()
        worker = self.auth.delegate(
            alice["instance_id"], alice["token"], capabilities={"chat.use"},
            ttl_seconds=60,
        )
        self.assertTrue(self.auth.require(worker["instance_id"], worker["token"], "chat.use"))
        self.now += 61
        with self.assertRaises(PermissionError):
            self.auth.require(worker["instance_id"], worker["token"], "chat.use")
        another = self.auth.delegate(
            alice["instance_id"], alice["token"], capabilities={"chat.use"},
        )
        self.auth.revoke(
            IrisInstanceAuthority.OWNER_ID, self.owner_secret,
            alice["instance_id"],
        )
        with self.assertRaises(PermissionError):
            self.auth.require(another["instance_id"], another["token"], "chat.use")

    def test_residente_nao_revoga_outro_cliente(self):
        alice = self.resident("cliente-alice")
        bob = self.resident("cliente-bob")
        with self.assertRaises(PermissionError):
            self.auth.revoke(alice["instance_id"], alice["token"], bob["instance_id"])
        self.assertTrue(self.auth.require(bob["instance_id"], bob["token"], "chat.use"))

    def test_feedback_exige_opt_in_e_nao_aceita_texto_livre(self):
        alice = self.resident()
        self.assertFalse(self.auth.report_feedback(alice["instance_id"], alice["token"], code="slow_response"))
        self.auth.set_resident_preferences(
            alice["instance_id"], alice["token"], feedback_opt_in=True,
        )
        with self.assertRaises(ValueError):
            self.auth.report_feedback(
                alice["instance_id"], alice["token"],
                code="conversa privada com senha de alguem",
            )
        self.assertTrue(
            self.auth.report_feedback(alice["instance_id"], alice["token"], code="slow_response")
        )
        self.assertFalse(
            self.auth.report_feedback(alice["instance_id"], alice["token"], code="slow_response")
        )
        self.assertEqual(self.auth.feedback_summary(self.owner_secret), {})

    def test_feedback_so_exibe_agregado_com_cinco_instalacoes(self):
        for number in range(5):
            resident = self.resident(f"cliente-{number:03d}")
            self.auth.set_resident_preferences(
                resident["instance_id"], resident["token"], feedback_opt_in=True,
            )
            self.auth.report_feedback(
                resident["instance_id"], resident["token"], code="unexpected_crash",
            )
        self.assertEqual(self.auth.feedback_summary(self.owner_secret), {"unexpected_crash": 5})
        with self.assertRaises(PermissionError):
            self.auth.feedback_summary("token-invalido")

    def test_identifier_validation_and_wrong_owner_credential(self):
        with self.assertRaises(ValueError):
            self.auth.create_resident(
                self.owner_secret, tenant_id="../outra-pessoa",
                display_name="Iris", user_consented=True,
            )
        with self.assertRaises(PermissionError):
            self.auth.create_resident(
                "segredo-invalido", tenant_id="cliente-001",
                display_name="Iris", user_consented=True,
            )


if __name__ == "__main__":
    unittest.main()
