"""Prueba mínima de T1: el bot ignora mensajes de chats no autorizados."""
import os, sys, unittest
from unittest import mock
from types import SimpleNamespace

os.environ["TELEGRAM_CHAT_ID"] = "111111"
os.environ["TELEGRAM_TOKEN"] = "123456:prueba"
os.environ["ANTHROPIC_API_KEY"] = "x"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402


def _msg(chat_id, user_id=999, text="busca procesos"):
    return SimpleNamespace(chat=SimpleNamespace(id=chat_id), text=text,
                           from_user=SimpleNamespace(id=user_id, username="alguien"))


class TestAutorizacion(unittest.TestCase):
    def test_chat_no_autorizado_no_llega_a_parse_intent(self):
        with mock.patch.object(main, "_parse_intent") as parse, \
             mock.patch.object(main.bot, "send_message") as send:
            main.handle_message(_msg(chat_id=222222))
            parse.assert_not_called()
            send.assert_not_called()

    def test_chat_autorizado_si_llega_a_parse_intent(self):
        with mock.patch.object(main, "_parse_intent", return_value={"accion": "otro"}) as parse, \
             mock.patch.object(main.bot, "send_message"), \
             mock.patch.object(main, "db_manager"):
            try:
                main.handle_message(_msg(chat_id=111111))
            except Exception:
                pass  # lo que pase después de la autorización no es objeto de esta prueba
            parse.assert_called_once()


if __name__ == "__main__":
    unittest.main()


class TestErroresNoSeDifunden(unittest.TestCase):
    """T5: el detalle del error va al log, al chat solo un texto fijo."""

    def test_error_en_job_manda_texto_fijo(self):
        with mock.patch.object(main.secop_scraper, "run_scrape", side_effect=RuntimeError("token invalido SECRETO-XYZ")), \
             mock.patch.object(main, "_broadcast") as bc, \
             mock.patch.object(main.db_manager, "log_run"), \
             self.assertLogs("main", level="ERROR") as logs:
            main._run_secop_job(3)
        bc.assert_called_once_with("Se presentó un error. El detalle quedó en el registro del sistema.")
        self.assertNotIn("SECRETO-XYZ", str(bc.call_args))
        self.assertTrue(any("SECRETO-XYZ" in l for l in logs.output))


class TestManejadorExcepcionesTelegram(unittest.TestCase):
    """El exception_handler de TeleBot debe exponer .handle(); si no, cada timeout de red rompe el polling."""

    def test_exception_handler_tiene_handle(self):
        main._registrar_exception_handler()
        self.assertTrue(hasattr(main.bot.exception_handler, "handle"))

    def test_timeout_de_red_no_molesta_al_usuario(self):
        main._registrar_exception_handler()
        with mock.patch.object(main, "_broadcast") as bc:
            resultado = main.bot.exception_handler.handle(TimeoutError("read timed out"))
        self.assertTrue(resultado)   # True = manejado, TeleBot no reinicia el polling
        bc.assert_not_called()

    def test_error_real_avisa_con_texto_fijo(self):
        main._registrar_exception_handler()
        with mock.patch.object(main, "_broadcast") as bc, self.assertLogs("main", level="ERROR"):
            resultado = main.bot.exception_handler.handle(ValueError("algo raro SECRETO-ABC"))
        self.assertTrue(resultado)
        bc.assert_called_once_with("Se presentó un error. El detalle quedó en el registro del sistema.")
