# -*- coding: utf-8 -*-

from functools import reduce
from lxml import etree
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang


class ResPartnet(models.Model):
    _inherit = "res.partner"

    def do_invoice_due_partner_mail(self):
        ctx = self.env.context.copy()
        ctx["ik_partner_invoice_due"] = True
        template = "ik_partner_invoice_due.email_template_partner_invoice_due_default"
        unknown_mails = 0
        for partner in self:
            partners_to_email = [
                child
                for child in partner.child_ids
                if child.type == "invoice" and child.email
            ]
            if not partners_to_email and partner.email:
                partners_to_email = [partner]
            if partners_to_email:
                level = partner.latest_followup_level_id_without_lit
                for partner_to_email in partners_to_email:
                    if (
                        level
                        and level.send_email
                        and level.email_template_id
                        and level.email_template_id.id
                    ):
                        level.email_template_id.with_context(ctx).send_mail(
                            partner_to_email.id
                        )
                    else:
                        mail_template_id = self.env.ref(template)
                        mail_template_id.with_context(ctx).send_mail(
                            partner_to_email.id
                        )
                if partner not in partners_to_email:
                    partner.message_post(
                        body=_(
                            "Overdue email sent to %s"
                            % ", ".join(
                                [
                                    "%s <%s>" % (partner.name, partner.email)
                                    for partner in partners_to_email
                                ]
                            )
                        )
                    )
            else:
                unknown_mails = unknown_mails + 1
        return unknown_mails

    invoice_due_ids = fields.One2many(
        "account.move",
        "partner_id",
        domain=[
            ("move_type", "=", "out_invoice"),
            ("payment_state", "in", ("not_paid", "partial")),
            ("state", "=", "posted"),
        ],
    )

    invoice_amount_due = fields.Float(
        compute="_compute_total", string="Total", store=False
    )

    @api.depends("invoice_due_ids")
    def _compute_total(self):
        for partner in self:
            amount_total = sum(partner.invoice_due_ids.mapped("amount_residual_signed"))
            partner.invoice_amount_due = amount_total

    message_template = fields.Text(
        "Printed Message Template",
        default="""
        <p style="box-sizing:border-box;margin-bottom: 0px;"> Estimado Cliente, {partner_name},</p>
        <p style="box-sizing:border-box;margin-bottom: 0px;"><br></p>
        <p style="box-sizing:border-box;margin-bottom: 0px;">Por este medio informamos que el siguiente estado de cuenta, se encuentra en estado pendiente, solicitamos realizar los pagos de manera oportuna, de lo contrario procederemos a suspender sus servicios.</p>
        <p style="box-sizing:border-box;margin-bottom: 0px;"><br></p>
        <p style="box-sizing:border-box;margin-bottom: 0px;">Favor realizar sus pagos en <a href="https://clientes.itelkom.co/" target="_blank" style="text-decoration:none;box-sizing:border-box;color:#66598f;">itelkom.co</a> botón PAGAR MI FACTURA.</p>
        <p style="box-sizing:border-box;margin-bottom: 0px;"><br></p>
        <p style="box-sizing:border-box;margin-bottom: 0px;">Si ya hubiera realizado el pago, agradezco nos envíe la información de este a: <a href="mailto:facturacion@itelkom.co">facturacion@itelkom.co</a> En caso de presentar alguna duda comuníquese a 3168312841 de lunes a viernes de 8am a 6pm.</p>
        <p style="box-sizing:border-box;margin-bottom: 0px;"><br></p>
        <p style="box-sizing:border-box;margin-bottom: 0px;"><br></p>
        """,
    )

    def get_formatted_message(self):
        return self.message_template.format(partner_name=self.name)


class AccountMove(models.Model):
    _inherit = "account.move"

    excluded_to_send = fields.Boolean(string="Excluded", default=False)
