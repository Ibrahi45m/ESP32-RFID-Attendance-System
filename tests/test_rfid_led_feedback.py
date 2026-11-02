import unittest
from unittest.mock import Mock
from rfid_led_feedback import couleur_pour_statut, encoder_commande, envoyer_feedback


class LEDFeedbackTests(unittest.TestCase):
    def test_validated_green(self):
        self.assertEqual(couleur_pour_statut('ok'), 'GREEN')
    def test_duplicate_white(self):
        self.assertEqual(couleur_pour_statut('deja'), 'WHITE')
    def test_out_of_group_white(self):
        self.assertEqual(couleur_pour_statut('hors_groupe'), 'WHITE')
    def test_window_closed_white(self):
        self.assertEqual(couleur_pour_statut('ferme'), 'WHITE')
    def test_unknown_white(self):
        self.assertEqual(couleur_pour_statut('inconnue'), 'WHITE')
    def test_other_denials_white(self):
        for statut in ('sans_groupe', 'conflit', 'erreur', 'inscription', 'aucune_seance', 'attente'):
            with self.subTest(statut=statut):
                self.assertEqual(couleur_pour_statut(statut), 'WHITE')
    def test_frame_bytes(self):
        self.assertEqual(encoder_commande('GREEN'), b'LED:GREEN\n')
        self.assertEqual(encoder_commande('WHITE'), b'LED:WHITE\n')
    def test_unsupported_color(self):
        with self.assertRaises(ValueError):
            encoder_commande('RED')
    def test_send_green_through_single_port(self):
        fake = Mock()
        fake.write.return_value = len(b'LED:GREEN\n')
        printed = Mock()
        res = envoyer_feedback(fake, 'GREEN', afficher=printed)
        self.assertEqual(res, b'LED:GREEN\n')
        fake.write.assert_called_once_with(b'LED:GREEN\n')
        fake.flush.assert_called_once_with()
    def test_partial_serial_write_is_error(self):
        fake = Mock()
        fake.write.return_value = 1
        with self.assertRaises(OSError):
            envoyer_feedback(fake, 'WHITE', afficher=Mock())
        fake.flush.assert_not_called()
    def test_send_closed_window_white(self):
        fake = Mock()
        fake.write.return_value = len(b'LED:WHITE\n')
        envoyer_feedback(fake, couleur_pour_statut('ferme'), afficher=Mock())
        fake.write.assert_called_once_with(b'LED:WHITE\n')


if __name__ == '__main__':
    unittest.main()
