from odoo import models, fields, api, _
from odoo.fields import Command

class TailoringMeasurementWizard(models.TransientModel):
    _name = 'tailoring.measurement.wizard'
    _description = 'Tailoring Measurement Wizard'

    line_id = fields.Many2one('tailoring.order.line')
    garment_type_id = fields.Many2one(related='line_id.product_id.garment_type_id')
    metric_line_ids = fields.One2many('tailoring.measurement.wizard.metric', 'wizard_id')
    spec_line_ids = fields.One2many('tailoring.measurement.wizard.spec', 'wizard_id')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line = self.env['tailoring.order.line'].browse(self.env.context.get('default_line_id'))
        if line and line.product_id.garment_type_id:
            g_type = line.product_id.garment_type_id
            res['metric_line_ids'] = [Command.create({'metric_id': m.id}) for m in g_type.metric_ids]
            res['spec_line_ids'] = [Command.create({'spec_id': s.id}) for s in g_type.spec_ids]
        return res

    def action_save(self):
        summary = []
        for m in self.metric_line_ids:
            summary.append(f"{m.metric_id.name}: {m.value}")
        for s in self.spec_line_ids:
            if s.value_id: summary.append(f"{s.spec_id.name}: {s.value_id.name}")
        self.line_id.measurement_summary = "\n".join(summary)
        return {'type': 'ir.actions.act_window_close'}

class TailoringMeasurementWizardMetric(models.TransientModel):
    _name = 'tailoring.measurement.wizard.metric'
    _description = 'Tailoring Measurement Wizard Metric'

    wizard_id = fields.Many2one('tailoring.measurement.wizard')
    metric_id = fields.Many2one('tailoring.metric.definition', readonly=True)
    value = fields.Float("Value")

class TailoringMeasurementWizardSpec(models.TransientModel):
    _name = 'tailoring.measurement.wizard.spec'
    _description = 'Tailoring Measurement Wizard Spec'

    wizard_id = fields.Many2one('tailoring.measurement.wizard')
    spec_id = fields.Many2one('tailoring.spec.definition', readonly=True)
    value_id = fields.Many2one('tailoring.spec.value', domain="[('spec_id', '=', spec_id)]")
