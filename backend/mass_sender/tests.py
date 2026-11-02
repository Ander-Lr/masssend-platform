import json
from unittest.mock import patch

import pyotp
from django.conf import settings
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from billing.services import wallet_service

from .admin import _send_campaign_background
from .models import Campaign, Contact, Message
from .services import ContactService, destinatarios_campana, normalizar_telefono

User = get_user_model()


class CampaignOwnershipRegressionTest(TestCase):
    """
    Regression test for the IDOR (insecure direct object reference)
    vulnerability found during the P2 evaluation via the V6 security
    matrix (benchmark/seguridad_tokens.py): before the fix,
    api_campanas_detail / api_campanas_media / api_campanas_ejecutar
    validated that a request carried a valid session or JWT
    (authentication) but never checked whether that user owned the
    requested campaign (authorization) -- so any authenticated user
    could read or execute *any* campaign by guessing its numeric id.

    The fix added an `owner` FK on Campaign and the `_es_dueno_o_staff`
    helper, checked in the three views above. This test keeps that fix
    honest going forward: it fails loudly if the ownership check is
    ever removed or weakened again.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username='owner_user', password='testpass123')
        self.other = User.objects.create_user(username='other_user', password='testpass123')
        self.staff = User.objects.create_user(username='staff_user', password='testpass123', is_staff=True)
        self.campaign = Campaign.objects.create(
            owner=self.owner,
            name='Campaign owned by owner_user',
            message_template='Hola {{nombre}}',
        )

    def _detail_url(self):
        return reverse('mass_sender:api_campanas_detail', args=[self.campaign.id])

    def test_owner_can_access_own_campaign(self):
        self.client.force_login(self.owner)
        resp = self.client.get(self._detail_url())
        self.assertEqual(resp.status_code, 200)

    def test_other_authenticated_user_is_rejected_idor(self):
        """
        The exact case that failed before the fix (returned 200 instead
        of 403): a different, fully authenticated user must NOT be able
        to read someone else's campaign just because they are logged in.
        """
        self.client.force_login(self.other)
        resp = self.client.get(self._detail_url())
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get('error'), 'No autorizado')

    def test_staff_can_access_any_campaign(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self._detail_url())
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_request_is_rejected(self):
        resp = self.client.get(self._detail_url())
        self.assertEqual(resp.status_code, 401)


def _json(client, method, url, body=None):
    return getattr(client, method)(url, json.dumps(body or {}), content_type='application/json')


class ContactIsolationTest(TestCase):
    """Cada usuario solo ve y modifica sus contactos y mensajes; el staff ve todo."""

    def setUp(self):
        self.ana = User.objects.create_user(username='ana', password='testpass123')
        self.luis = User.objects.create_user(username='luis', password='testpass123')
        self.staff = User.objects.create_user(username='jefe', password='testpass123', is_staff=True)
        self.contacto_ana = Contact.objects.create(owner=self.ana, phone_number='593991111111')
        Message.objects.create(owner=self.ana, phone_number='593991111111', content='hola', direction='outbound')

    def test_otro_usuario_no_ve_datos_ajenos(self):
        self.client.force_login(self.luis)
        self.assertEqual(self.client.get('/whatsapp/api/contactos/').json()['total'], 0)
        self.assertEqual(self.client.get('/whatsapp/api/mensajes/').json()['total'], 0)
        self.assertEqual(self.client.get('/whatsapp/api/reportes/').json()['resumen']['enviados'], 0)

    def test_otro_usuario_no_modifica_ni_borra_datos_ajenos(self):
        self.client.force_login(self.luis)
        url = f'/whatsapp/api/contactos/{self.contacto_ana.id}/'
        self.assertEqual(_json(self.client, 'put', url, {'nombre': 'x'}).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        _json(self.client, 'post', '/whatsapp/api/contactos/bulk-delete/', {'ids': [self.contacto_ana.id]})
        self.assertTrue(Contact.objects.filter(pk=self.contacto_ana.pk).exists())

    def test_staff_ve_todo(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/whatsapp/api/contactos/').json()['total'], 1)

    def test_dos_usuarios_pueden_tener_el_mismo_numero(self):
        self.client.force_login(self.luis)
        resp = _json(self.client, 'post', '/whatsapp/api/contactos/', {'telefono': '0991111111'})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Contact.objects.filter(phone_number='593991111111').count(), 2)

    def test_progreso_de_campana_ajena_rechazado(self):
        campana = Campaign.objects.create(owner=self.ana, name='c', message_template='m')
        self.client.force_login(self.luis)
        self.assertEqual(self.client.get(f'/whatsapp/api/campaign-progress/{campana.id}/').status_code, 403)

    @override_settings(WHATSAPP_WEBHOOK_TOKEN='tok')
    def test_respuesta_entrante_llega_a_quien_escribio(self):
        Contact.objects.create(owner=self.luis, phone_number='593991111111')
        resp = self.client.post(
            '/whatsapp/api/webhook/', json.dumps({'from': '593991111111', 'body': 'gracias'}),
            content_type='application/json', HTTP_AUTHORIZATION='Bearer tok',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Message.objects.get(direction='inbound').owner, self.ana)

    @override_settings(WHATSAPP_WEBHOOK_TOKEN='tok')
    def test_numero_desconocido_queda_sin_dueno(self):
        self.client.post(
            '/whatsapp/api/webhook/', json.dumps({'from': '593992222222', 'body': 'hola'}),
            content_type='application/json', HTTP_AUTHORIZATION='Bearer tok',
        )
        self.assertIsNone(Contact.objects.get(phone_number='593992222222').owner)


class CampaignExecutionTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user(username='ana', password='testpass123')
        self.luis = User.objects.create_user(username='luis', password='testpass123')
        self.c1 = Contact.objects.create(owner=self.ana, phone_number='593991111111', tags='vip')
        self.c2 = Contact.objects.create(owner=self.ana, phone_number='593992222222', tags='cliente')
        Contact.objects.create(owner=self.ana, phone_number='593993333333', tags='lead')
        Contact.objects.create(owner=self.luis, phone_number='593994444444', tags='vip')
        self.campana = Campaign.objects.create(owner=self.ana, name='c', message_template='m', target_tags='vip, cliente')
        self.client.force_login(self.ana)

    def test_destinatarios_solo_del_dueno_y_cualquier_etiqueta(self):
        self.assertEqual(set(destinatarios_campana(self.campana)), {self.c1, self.c2})

    @patch('mass_sender.views.default_gateway.status', return_value={'ready': False})
    def test_whatsapp_desconectado_no_cobra(self, _status):
        saldo = wallet_service.get_balance(self.ana)
        resp = self.client.post(f'/whatsapp/api/campanas/{self.campana.id}/ejecutar/')
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(wallet_service.get_balance(self.ana), saldo)

    @patch('mass_sender.admin.time.sleep')
    @patch('mass_sender.admin.requests.post')
    @patch('django.db.connection.close')
    def test_fallos_del_gateway_devuelven_creditos(self, _close, post, _sleep):
        post.return_value.status_code = 503
        post.return_value.text = 'caido'
        saldo = wallet_service.get_balance(self.ana)
        wallet_service.spend_credits(self.ana, 2)
        _send_campaign_background(self.campana.id, [self.c1.id, self.c2.id], cobrado_a=self.ana)
        self.assertEqual(wallet_service.get_balance(self.ana), saldo)
        self.assertEqual(Message.objects.filter(owner=self.ana, delivery_status='failed').count(), 2)


class ChatAndGatewayCallbacksTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ana', password='testpass123')
        self.staff = User.objects.create_user(username='jefe', password='testpass123', is_staff=True)

    def test_chat_exige_staff(self):
        self.assertEqual(self.client.get('/whatsapp/api/chat/mensajes/').status_code, 401)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/whatsapp/api/chat/mensajes/').status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/whatsapp/api/chat/mensajes/').status_code, 200)

    def test_chat_informa_fallo_si_gateway_caido(self):
        self.client.force_login(self.staff)
        with patch('mass_sender.services.WhatsAppGateway.send', side_effect=OSError('caido')):
            resp = _json(self.client, 'post', '/whatsapp/api/chat/enviar/', {'to': '593991111111', 'message': 'hola'})
        self.assertFalse(resp.json()['success'])
        self.assertEqual(Message.objects.get().delivery_status, 'failed')

    def test_chat_encola_y_queda_pendiente(self):
        self.client.force_login(self.staff)
        with patch('mass_sender.services.WhatsAppGateway.send', return_value={'success': True}):
            _json(self.client, 'post', '/whatsapp/api/chat/enviar/', {'to': '593991111111', 'message': 'hola'})
        self.assertEqual(Message.objects.get().delivery_status, 'pending')

    @override_settings(WHATSAPP_WEBHOOK_TOKEN='tok')
    def test_ack_sin_id_no_rompe(self):
        resp = self.client.post(
            '/whatsapp/api/message-ack/',
            json.dumps({'wpp_message_id': None, 'number': '593991111111', 'status': 'sent'}),
            content_type='application/json', HTTP_AUTHORIZATION='Bearer tok',
        )
        self.assertEqual(resp.status_code, 200)

    @override_settings(WHATSAPP_WEBHOOK_TOKEN='tok')
    def test_send_result_resuelve_el_pendiente_mas_antiguo(self):
        primero = Message.objects.create(phone_number='593991111111', content='1', direction='outbound')
        segundo = Message.objects.create(phone_number='593991111111', content='2', direction='outbound')
        self.client.post(
            '/whatsapp/api/send-result/',
            json.dumps({'number': '593991111111', 'status': 'sent', 'wpp_message_id': 'X'}),
            content_type='application/json', HTTP_AUTHORIZATION='Bearer tok',
        )
        primero.refresh_from_db(); segundo.refresh_from_db()
        self.assertEqual((primero.delivery_status, segundo.delivery_status), ('sent', 'pending'))


class NormalizarTelefonoTest(TestCase):
    def test_casos(self):
        self.assertEqual(normalizar_telefono('099 111-2222'), ('593991112222', None))
        self.assertIsNotNone(normalizar_telefono('022345678')[1])

    def test_importar_normaliza(self):
        ContactService.importar_lote([{'telefono': '0991112222'}])
        self.assertTrue(Contact.objects.filter(phone_number='593991112222').exists())


class MfaLoginFlowTest(TestCase):
    """Activar MFA y volver a iniciar sesión con el código del autenticador."""

    def setUp(self):
        User.objects.create_user(username='ana@test.local', email='ana@test.local', password='testpass123')
        self.credenciales = {'email': 'ana@test.local', 'password': 'testpass123'}
        _json(self.client, 'post', '/api/email-auth/auth/login-step1/', self.credenciales)
        self.clave = _json(self.client, 'post', '/api/email-auth/mfa/setup/').json()['manualKey']
        self.activar = _json(self.client, 'post', '/api/email-auth/mfa/confirm/', {'code': pyotp.TOTP(self.clave).now()})

    def test_activar_mfa_deja_sesion_con_duracion_normal(self):
        self.assertEqual(self.activar.status_code, 200)
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    def test_segundo_inicio_de_sesion_con_codigo(self):
        self.client.logout()
        _json(self.client, 'post', '/api/email-auth/auth/login-step1/', self.credenciales)
        resp = _json(self.client, 'post', '/api/email-auth/auth/login-step2/', {'code': pyotp.TOTP(self.clave).now()})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.get('/whatsapp/api/auth/me/').status_code, 200)
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)
