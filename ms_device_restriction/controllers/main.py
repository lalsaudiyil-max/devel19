import logging
import json
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.web.controllers.home import Home

_logger = logging.getLogger(__name__)

class StrictHardwareGatekeeper(Home):

    # FIXED: Use auth="public" and website=True so Odoo Enterprise web templates have their required context variables!
    @http.route('/web/login', type='http', auth="public", website=True, sitemap=False)
    def web_login(self, redirect=None, **kw):
        if request.httprequest.method == 'POST':
            
            # --- 1. EXTRACT DATA MATRICES ---
            login_username = None
            hw_uuid = None
            comp_name = 'Unknown Node'

            if request.params:
                hw_uuid = request.params.get('hardware_uuid')
                comp_name = request.params.get('computer_name', 'Unknown Node')
                login_username = request.params.get('login')

            if not hw_uuid and request.httprequest.data:
                try:
                    raw_data = json.loads(request.httprequest.data.decode('utf-8'))
                    rpc_params = raw_data.get('params', {})
                    hw_uuid = rpc_params.get('hardware_uuid')
                    comp_name = rpc_params.get('computer_name', 'Unknown Node')
                    if not login_username:
                        login_username = rpc_params.get('login')
                except Exception:
                    pass

            if not hw_uuid:
                hw_uuid = kw.get('hardware_uuid')
                comp_name = kw.get('computer_name', 'Unknown Node')
                if not login_username:
                    login_username = kw.get('login')

            _logger.info("Gatekeeper Framework Hook - Username: %s | Hardware ID: %s", login_username, hw_uuid)

            # --- 2. EVALUATE USER RULES ---
            user = request.env['res.users'].sudo().search([('login', '=', login_username)], limit=1)
            
            # If the user doesn't exist, or has device protection turned off, pass cleanly to standard routine
            if not user or not user.enable_device_restriction:
                _logger.info("Gatekeeper: Authentication restriction bypassed for user '%s'.", login_username)
                return super(StrictHardwareGatekeeper, self).web_login(redirect=redirect, **kw)

            # --- HIGH-STABILITY CUSTOM ERROR SCREEN LAYOUT ---
            def error_response_page(message):
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Access Denied</title>
                    <link rel="stylesheet" href="/web/static/lib/bootstrap/css/bootstrap.min.css"/>
                    <style>
                        body {{ background: #f8f9fa; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                        .card {{ border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); padding: 2rem; max-width: 450px; text-align: center; background: #fff; }}
                        .btn-primary {{ background: #714B67; border-color: #714B67; }}
                    </style>
                </head>
                <body>
                    <div class="card border-0">
                        <div class="text-danger mb-3">
                            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="currentColor" class="bi bi-shield-lock" viewBox="0 0 16 16">
                              <path d="M8 1a2 2 0 0 1 2 2v4H6V3a2 2 0 0 1 2-2zm3 6V3a3 3 0 0 0-6 0v4a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z"/>
                            </svg>
                        </div>
                        <h4 class="text-dark mb-3">Security Device Restriction</h4>
                        <p class="text-muted mb-4">{message}</p>
                        <a href="/web/login" class="btn btn-primary w-100 py-2 text-white text-decoration-none rounded">Return to Login</a>
                    </div>
                </body>
                </html>
                """
                return request.make_response(html_content, headers=[('Content-Type', 'text/html')])

            # --- 3. STRICT DUAL-KEY SECURITY MATCHING ---
            if not hw_uuid or hw_uuid == 'pending-js-eval':
                _logger.warning("Gatekeeper Block: Aborted due to unpopulated hardware identities.")
                return error_response_page(_("Access Denied: Browser environment metrics are isolated or restricted."))

            # Admins (group_system) and root user (ID 1) bypass device verification rules completely
            if not (user.has_group('base.group_system') or user.id == 1):
                device_record = request.env['res.users.device'].sudo().search([
                    ('user_id', '=', user.id),
                    ('hardware_uuid', '=', hw_uuid)
                ], limit=1)

                if not device_record:
                    existing_pending = request.env['res.users.device'].sudo().search([
                        ('user_id', '=', user.id),
                        ('hardware_uuid', '=', hw_uuid),
                        ('state', '=', 'pending')
                    ], limit=1)

                    if not existing_pending:
                        request.env['res.users.device'].sudo().create({
                            'user_id': user.id,
                            'hardware_uuid': hw_uuid,
                            'computer_name': f"{user.name}'s {comp_name}",
                            'state': 'pending'
                        })
                        request.env.cr.commit()

                    _logger.warning("Gatekeeper Block: Unrecognized link. User '%s' is not authorized to use Hardware ID '%s'.", login_username, hw_uuid)
                    return error_response_page(_("Access Denied: This computer is unrecognized for your account. A registration request has been submitted to your administrator."))

                if device_record.state != 'approved':
                    status_msg = _("is pending admin authorization.") if device_record.state == 'pending' else _("has been restricted.")
                    return error_response_page(f"{_('Access Denied: This terminal hardware')} ({device_record.computer_name}) {status_msg}")

                device_record.sudo().write({'last_login': fields.Datetime.now()})
                request.env.cr.commit()

        # Execute standard login page operations natively
        response = super(StrictHardwareGatekeeper, self).web_login(redirect=redirect, **kw)
        
        # Keep authentication session tokens active across app restarts for 1 year
        if request.httprequest.method == 'POST' and request.session.uid:
            remember_me_duration = 365 * 24 * 60 * 60
            response.set_cookie(
                'sid', 
                request.session.sid, 
                max_age=remember_me_duration, 
                httponly=True, 
                samesite='Lax'
            )
            _logger.info("Gatekeeper: Successfully hardened session token for 365 days persistent stay.")

        return response
