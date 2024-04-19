from odoo import api, fields, models, _
from odoo.tools.mail import html2plaintext, is_html_empty


class MilitaryEmployeeMove(models.Model):
    _name = "military.employee.move"
    _description = "Staff Move"
    _rec_names_search = ['name', 'employee_id.name']
    _inherit = "mail.thread"
    _order = "id desc"

    name = fields.Char(
        'Number',
        copy=False,
    )
    origin = fields.Char(
        'Basis',
        index=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Basis of the movement"
    )
    note = fields.Text('Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ],
        string='Status',
        compute='_compute_state',
        default='draft',
        copy=False,
        index=True,
        readonly=True,
        store=True,
        tracking=True,
    )
    date = fields.Date(
        'Move Date',
        default=fields.Date.today(),
        index=True,
        tracking=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
    )
    location_id = fields.Many2one(
        'military.employee.location',
        "Destination Location",
        readonly=True,
        required=True,
        states={'draft': [('readonly', False)]}
    )
    move_line_ids = fields.One2many(
        'military.employee.move.line',
        'move_id',
        'Operations',
        copy=True
    )
    move_type_id = fields.Many2one(
        'military.employee.move.type',
        'Move Type',
        required=True,
        readonly=False,
        states={'draft': [('readonly', False)]}
    )
    move_type_code = fields.Selection(
        related='move_type_id.code',
        readonly=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        'Partner',
        check_company=True,
        states={'done': [('readonly', True)],
                'cancel': [('readonly', True)]}
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        readonly=True,
        store=True,
        index=True
    )
    user_id = fields.Many2one(
        'res.users',
        'Responsible',
        tracking=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        default=lambda self: self.env.user)
    employee_ids = fields.Many2one(
        'military.employee',
        'Employee',
        related='move_line_ids.employee_id',
        readonly=True
    )

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        for move in self:
            move_id = isinstance(move.id, int) and move.id or getattr(move, '_origin',
                                                                      False) and move._origin.id
            if move_id:
                moves = self.env['military.employee.move.line'].search([('move_id', '=', move_id)])
                for move in moves:
                    move.write({'partner_id': move.partner_id.id})

    @api.onchange('move_type_id')
    def onchange_move_type_id(self):
        for move in self:
            move.location_id = move.move_type_id.location_id


class MilitaryEmployeeMoveLine(models.Model):
    _name = "military.employee.move.line"
    _description = "Employee Move"
    _order = 'id desc'

    name = fields.Char(
        'Description',
        index=True,
        required=True
    )
    sequence = fields.Integer('Sequence', default=1)
    create_date = fields.Datetime(
        'Creation Date',
        index=True,
        readonly=True
    )
    date = fields.Date(
        'Move Date',
        related='move_id.date',
        index=True,
        store=True,
    )
    end_date = fields.Datetime(
        'Move End Date', index=True
    )
    company_id = fields.Many2one(
        'res.company',
        related='move_id.company_id',
        default=lambda self: self.env.company,
        index=True,
        required=True)
    employee_id = fields.Many2one(
        'military.employee', 'Employee',
        check_company=True,
        # domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        index=True, required=True,
        states={'done': [('readonly', True)]})
    description = fields.Text('Description of Move')
    location_id = fields.Many2one(
        'military.employee.location',
        'Source Location',
        auto_join=True,
        index=True,
    )
    location_dest_id = fields.Many2one(
        'military.employee.location',
        'Destination Location',
        auto_join=True,
        index=True,
        required=True,
        help="Location where the system will locate the Employee."
    )
    partner_id = fields.Many2one(
        'res.partner',
        'Source Address',
        states={'done': [('readonly', True)]},
        help="Optional address where Employee is Located")
    partner_dest_id = fields.Many2one(
        'res.partner',
        'Destination Address',
        states={'done': [('readonly', True)]},
        help="Optional address where Employee is to be moved")
    move_id = fields.Many2one(
        'military.employee.move',
        'Move',
        index=True,
        states={'done': [('readonly', True)]},
        check_company=True)
    move_partner_id = fields.Many2one(
        'res.partner',
        'Move Destination Address',
        related='move_id.partner_id',
        readonly=False)
    note = fields.Text('Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ],
        string='Status',
        copy=False,
        default='draft',
        index=True,
        readonly=True,
        help="* Draft: When the move is created and not yet confirmed.\n"
             "* Done: When the move is processed, the state is \'Done\'.")
    origin = fields.Char("Basis")
    move_type_id = fields.Many2one(
        'military.employee.move.type',
        'Operation Type',
        check_company=True)
    # inventory_id = fields.Many2one(
    #     'military.employee.inventory',
    #     'Inventory',
    #     check_company=True)

    def _get_description(self, move_type_id):
        """ return employee move description depending on
        picking type passed as argument.
        """
        self.ensure_one()
        move_code = move_type_id.code
        description = html2plaintext(self.description) if not is_html_empty(
            self.description) else self.name
        if move_code == 'incoming':
            return self.move_type_id.description or self.name
        if move_code == 'outgoing':
            return self.move_type_id.description or self.name
        if move_code == 'internal':
            return self.move_type_id.description or self.name
        return description

    @api.onchange('employee_id', 'move_type_id')
    def onchange_employee(self):
        if self.employee_id:
            self.description = self._get_description(self.move_type_id)
            self.location_id = self.employee_id.location_id or ''
            self.location_dest_id = self.move_id.location_id or ''

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            if self.move_id:
                # employee = self.employee_id
                self.description = self._get_description(self.move_id.move_type_id)


class MilitaryEmployeeMoveType(models.Model):
    _name = "military.employee.move.type"
    _description = "Staff Move Type"
    _order = "name asc"

    name = fields.Char(
        'Operation Type',
        required=True
    )
    color = fields.Integer('Color')
    location_id = fields.Many2one(
        'military.employee.location',
        'Default Destination Location',
        check_company=True,
        help="This is the default destination location when you create a move manually with this operation type."
    )
    code = fields.Selection(
        [('incoming', 'Arrival'),
         ('outgoing', 'Departure'),
         ('internal', 'Internal')
         ], 'Type of Operation',
        required=True
    )
    report_ids = fields.Many2one(
        'ir.actions.report',
        string='Reports',
        domain="[('model', '=', 'military.employee.move')]"
    )
    description = fields.Text('Description of Move')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        index=True,
        default=lambda self: self.env.company
    )