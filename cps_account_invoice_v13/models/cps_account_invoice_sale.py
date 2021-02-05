# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import date
from odoo.exceptions import UserError, AccessError, Warning

to_19_fr = (u'zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six',
          'sept', 'huit', 'neuf', 'dix', 'onze', 'douze', 'treize',
          'quatorze', 'quinze', 'seize', 'dix-sept', 'dix-huit', 'dix-neuf')
tens_fr = ('vingt', 'trente', 'quarante', 'Cinquante', 'Soixante', 'Soixante-dix', 'Quatre-vingts', 'Quatre-vingt Dix')
denom_fr = ('',
          'Mille', 'Millions', 'Milliards', 'Billions', 'Quadrillions',
          'Quintillion', 'Sextillion', 'Septillion', 'Octillion', 'Nonillion',
          'Décillion', 'Undecillion', 'Duodecillion', 'Tredecillion', 'Quattuordecillion',
          'Sexdecillion', 'Septendecillion', 'Octodecillion', 'Icosillion', 'Vigintillion')

class AccountInvoiceSale(models.Model):
    _name = 'account.invoice.sale'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Liste des factures'

    name_facture = fields.Char(related="account_move_id.name", string="N° Facture")
    prestation_type = fields.Char('Type préstation')
    client_id = fields.Many2one("res.partner", 'Client de livraison', domain=[('is_client_principal', '=', False),('is_atelier', '=', False),('supplier_rank', '=', 0),('is_company', '=', True)], required=True)
    client_fact_id = fields.Many2one("res.partner", 'Client de facturation', domain=[('is_client_principal', '=', False),('is_atelier', '=', False),('supplier_rank', '=', 0),('is_company', '=', True)], required=True)
    atelier_id = fields.Many2one("res.partner", 'Atelier', domain=[('is_atelier', '=', True),('supplier_rank', '=', 0),('is_company', '=', True)])
    date_facture = fields.Date("Date Facture", required=True)
    payment_method = fields.Many2one('account.journal', 'Journal', domain=[('type', '=', 'sale')])
    payment_term_id = fields.Many2one('account.payment.term', "Echéance")
    sale_order_ids = fields.One2many('sale.order', "netline_facturation_id")

    account_move_id = fields.Many2one('account.move', 'Facture')
    state = fields.Selection(string="Etat de la Facture", selection=[('ready', 'Pret'),
                                                                     ('draft', 'Brouillon'),
                                                                     ('accounted', 'Comptabilisé'),
                                                                     ('cancelled', 'Annulé'),
                                                                     ], required=True, default='ready', track_visibility='always')
    date_echeance = fields.Date(related="account_move_id.invoice_date_due")
    currency_id = fields.Many2one('res.currency', string='Devise')
    invoice_totalht = fields.Monetary(related="account_move_id.amount_untaxed", string="Total HT")
    invoice_totaltva = fields.Monetary(related="account_move_id.amount_tax", string="Total T.V.A")
    invoice_totalttc = fields.Monetary(related="account_move_id.amount_total", string="Total TTC")

    facturation_lines_ids = fields.One2many('account.invoice.sale.line', 'facturation_id', string="Produits")
    amount_in_letters = fields.Char('Montant en lettre', compute='amount_to_text', store=True)
    name = fields.Char("name", compute="compute_name")
    ref= fields.Char(string='Prochaine facture')

    invoice_lines = []
    sale_order_origin = ""

    def amount_to_text(self):
        for p in self:
            p.amount_in_letters = self.convert_amount_to_text_fr(p.invoice_totalttc, p.currency_id.name)

    def compute_name(self):
        recs = []
        for p in self:
            name = "FACTURE N° " + str(p.id)
            p.name = name

    @api.depends('client_fact_id')
    @api.onchange('client_fact_id')
    def _compute_client_fact_id(self):
        if self.client_id is False:
            self.client_id=self.client_fact_id
        if len(self.client_fact_id.property_product_pricelist)>0:
            self.date_facture = date.today()
            self.payment_term_id = self.client_fact_id.property_payment_term_id.id
            price_list = self.env['product.pricelist'].search([('id', '=', self.client_fact_id.property_product_pricelist[0].id)])
            self.currency_id = price_list.currency_id.id
            account_journal = self.env['account.journal'].search([('currency_id', '=', price_list.currency_id.id), ('type', '=', 'sale')], limit=1)
            self.payment_method= account_journal.id
        # for l in self.facturation_lines_ids:
        #     l.assign_quantities()

    def unlink(self):
        if len(self.account_move_id) >0:
            if self.account_move_id.state!= 'cancel':
                raise UserError(_("Ce brouillon ne peut etre suprrimé car elle est liée avec une facture non annulée"))
        self.compute_lines()
        return super(AccountInvoiceSale, self).unlink()

    # @api.depends('client_id')
    # @api.onchange('client_id')
    # def _compute_client_id(self):
    #     for s in self:
    #         for l in s.facturation_lines_ids:
    #             l.unlink()
    #
    #
    #
    def action_invoice_cancel_wizard(self):
        self.account_move_id.button_draft()
        self.account_move_id.button_cancel()
        self.account_move_id.line_ids.unlink()
        self.compute_lines()
        self.state="cancelled"

    def compute_lines(self):
        if self.prestation_type=="Textil industrie":
            for facture_line in self.facturation_lines_ids:
                facture_line.product_id.template_ids.compute_all()
                facture_line.product_id.template_ids.product_tmpl_production_ids.compute_state_fact()

    def check_qty_lines(self):
        for facture_line in self.facturation_lines_ids:
            if facture_line.qty_to_invoice<=0:
                raise UserError(_("Merci de renseigner la quantité pour toute les lignes"))

    # def action_invoice_disacount_wizard(self):
        # self.account_move_id.button_draft()
        # self.facturation_lines_ids.account_move_line_ids.unlink()
        # self.invoice_create_lines_wizard()
        # self.check_qty_lines()
        # self.compute_lines()
        # self.state="draft"

    # def action_invoice_count_wizard(self):
    #     if self.account_move_id.name!="/":
    #         self.invoice_create_lines_wizard()
        # self.account_move_id.action_post()
        # self.account_move_id.date = self.date_facture
        # self.check_qty_lines()
        # self.compute_lines()
        # self.state="accounted"

    def action_invoice_create_wizard(self):
        #"creating cps facture"
        if len(self.account_move_id)==0:
            print('creation facture-------------------')
            self.check_qty_lines()
            self.invoice_lines = []
            self.sale_order_origin = ""
            account_journal = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
            invoice = self.env['account.move'].create({
                'partner_id': self.client_fact_id.id,
                'partner_shipping_id': self.client_id.id,
                'journal_id': account_journal.id,
                'type': 'out_invoice',
                'invoice_date': self.date_facture,
                'invoice_payment_term_id': self.payment_term_id.id,
                'currency_id': self.currency_id.id,
                'name': '/',
                'state': 'draft',
                })
            self.account_move_id= invoice.id
            self.state="draft"
        self.check_qty_lines()
        print('creation lignes facture-------------------')
        self.invoice_create_lines_wizard()
        self.account_move_id.action_post()
        self.account_move_id.date = self.date_facture
        self.compute_lines()
        self.state="accounted"
        if self.prestation_type != 'Textil industrie':
            for sale_order in self.sale_order_ids:
                for livraison in sale_order.netline_livraison_id:
                    livraison.set_invoiced()


    def invoice_create_lines_wizard(self):
        self.invoice_lines = []
        sols = []
        self.sale_order_origin = ""
        message=""
        warning = {}
        account_revenue = self.env['account.account'].search([('user_type_id', '=', self.env.ref('account.data_account_type_revenue').id)], limit=1)
        if self.prestation_type == 'Textil industrie':
            for facture_line in self.facturation_lines_ids:
                sols = self.env['sale.order.line'].search([("order_partner_id", "=", self.client_id.id),("product_id", "=", facture_line.product_id.id), ("qty_to_invoice", ">", 0)], order='create_date')
                qty_to_invoice_cal = facture_line.qty_to_invoice
                print('qty_to_invoice_cal------------------------', qty_to_invoice_cal)
                tax_id=False
                if len(facture_line.product_id) > 0:
                    for sol in sols :
                        if qty_to_invoice_cal>0:
                            if qty_to_invoice_cal > sol.product_uom_qty:
                                qty_to_invoice = sol.product_uom_qty
                            else:
                                qty_to_invoice = qty_to_invoice_cal
                            qty_to_invoice_cal -= sol.product_uom_qty
                            self.invoice_lines.append((0, 0, {
                                'product_id': sol.product_id.id,
                                'name': facture_line.product_description,
                                'quantity': qty_to_invoice,
                                'price_unit': facture_line.price,
                                'account_id': account_revenue.id,
                                'tax_ids': [(6, 0, sol.tax_id.ids)],
                                'sale_line_ids': [(6, 0, sol.ids)],
                                'facturation_line_id': facture_line.id
                            }))
                            self.sale_order_origin += sol.order_id.name + ", "
                            sol.order_id.write({'invoice_count': sol.order_id.invoice_count + 1, 'invoice_ids': (0, 0, self.account_move_id.id), 'invoice_status': 'invoiced'})
                            tax_id = sol.tax_id
                        else:
                            self.invoice_lines.append((0, 0, {
                                'quantity': qty_to_invoice_cal,
                                'price_unit': facture_line.price,
                                'name': facture_line.product_description,
                                'account_id': account_revenue.id,
                                'tax_ids': [(6, 0, sol.tax_id.ids if tax_id is not False else [])],
                                'sale_line_ids': [],
                                'facturation_line_id': facture_line.id
                            }))
            if qty_to_invoice_cal > 0:
                raise UserError(_("Attention, il n'existe aucun bon a facturer pour l'of " + facture_line.product_id.name + ", merci de reverifier la qté facturée !"))
        if self.prestation_type != 'Textil industrie':
            for so in self.facturation_lines_ids.facturation_id.sale_order_ids:
                sols += so.order_line
            qty_to_invoice_cal = 0
            for sol in sols:
                qty_to_invoice = sol.product_uom_qty
                qty_to_invoice_cal -= qty_to_invoice
                reception_line = sol.netline_livraison_line_ids[0].reception_line_id

                self.invoice_lines.append((0, 0, {
                    'product_id': reception_line.product_id.product_id.id,
                    'name': reception_line.product_id.product_id.description,
                    'quantity': qty_to_invoice,
                    'price_unit': sol.price_unit,
                    'account_id': account_revenue.id,
                    'tax_ids': [(6, 0, sol.tax_id.ids)],
                    'sale_line_ids': [(6, 0, sol.ids)],
                    # 'facturation_line_id': facture_line.id
                }))
                self.sale_order_origin += sol.order_id.name + ", "
                sol.order_id.write({'invoice_count': sol.order_id.invoice_count + 1, 'invoice_ids': (0, 0, self.account_move_id.id), 'invoice_status': 'invoiced'})
                tax_id = sol.tax_id

        if qty_to_invoice_cal>0:
            raise UserError(_("Attention, il n'existe aucun bon a facturer pour l'of " + facture_line.product_id.name + ", merci de reverifier la qté facturée !"))
            # else:
            #     self.invoice_lines.append((0, 0, {
            #         'quantity': qty_to_invoice_cal,
            #         'price_unit': facture_line.price,
            #         'name': facture_line.product_description,
            #         'account_id': account_revenue.id,
            #         'tax_ids': [(6, 0, sol.tax_id.ids if tax_id is not False else [])],
            #         'sale_line_ids': [],
            #         'facturation_line_id': facture_line.id
            #     }))
        self.account_move_id.write({'invoice_line_ids': self.invoice_lines, 'invoice_origin': self.sale_order_origin[:-2]})

    def action_view_invoice(self):
        if self.account_move_id.id is not False:

            result = {
                'name': "account.move.form",
                'view_type': 'form',
                'res_model': 'account.move',
                'res_id': self.account_move_id.id,
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'context' : {'form_view_ref': 'account.view_move_form'}
            }
            return result
        else :
            raise UserError(_("Aucune facture n'est encore disponible, cliquez sur valider"))


    def write(self, values):
        invoice = super(AccountInvoiceSale, self).write(values)
        if 'client_id' in values:
            if len(self.account_move_id)>0:
                self.account_move_id.partner_shipping_id=self.account_move_id.partner_id
                self.account_move_id.partner_id= values.get('client_id')
        if 'ref' in values:
            ir_sequence = self.env['ir.sequence'].search([('name', '=', 'FAC Séquence')])
            for date_range in ir_sequence.date_range_ids:
                date_range.number_next_actual = values['ref']
        return invoice

    @api.model
    def create(self, values):
        print('values ---------------------------------------', values)
        invoice = super(AccountInvoiceSale, self).create(values)
        if 'ref' in values:
            if values['ref']:
                ir_sequence = self.env['ir.sequence'].search([('name', '=', 'FAC Séquence')])
                for date_range in ir_sequence.date_range_ids:
                    date_range.number_next_actual = values['ref']
        return invoice


    def _convert_nn_fr(self, val):
        """ convert a value < 100 to French
        """
        if val < 20:
            return to_19_fr[val]
        for (dcap, dval) in ((k, 20 + (10 * v)) for (v, k) in enumerate(tens_fr)):
            if dval + 10 > val:
                if val % 10:
                    if dval == 70 or dval == 90:
                        return tens_fr[dval / 10 - 3] + '-' + to_19_fr[val % 10 + 10]
                    else:
                        return dcap + '-' + to_19_fr[val % 10]
                return dcap


    def _convert_nnn_fr(self, val):
        """ convert a value < 1000 to french

            special cased because it is the level that kicks
            off the < 100 special case.  The rest are more general.  This also allows you to
            get strings in the form of 'forty-five hundred' if called directly.
        """
        word = ''
        (mod, rem) = (val % 100, val // 100)
        if rem > 0:
            if rem == 1:
                word = 'Cent'
            else:
                word = to_19_fr[rem] + ' Cent'
            if mod > 0:
                word += ' '
        if mod > 0:
            word += self._convert_nn_fr(mod)
        return word


    def french_number(self, val):
        if val < 100:
            return self._convert_nn_fr(val)
        if val < 1000:
            return self._convert_nnn_fr(val)
        for (didx, dval) in ((v - 1, 1000 ** v) for v in range(len(denom_fr))):
            if dval > val:
                mod = 1000 ** didx
                l = val // mod
                r = val - (l * mod)
                if l == 1:
                    ret = denom_fr[didx]
                else:
                    ret = self._convert_nnn_fr(l) + ' ' + denom_fr[didx]
                if r > 0:
                    ret = ret + ', ' + self.french_number(r)
                return ret


    def convert_amount_to_text_fr(self, numbers, currency):
        number = '%.2f' % numbers
        units_name = currency
        liste = str(number).split('.')
        start_word = self.french_number(abs(int(liste[0])))
        end_word = self.french_number(int(liste[1]))
        cents_number = int(liste[1])
        cents_name = (cents_number > 1) and ' Centimes' or ' Centime'
        final_result = start_word + ' ' + units_name + ' ' + end_word + ' ' + cents_name
        return final_result
