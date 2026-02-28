from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    customer_type = db.Column(db.String(50))  # residential/commercial
    contact_info = db.Column(db.String(255))
    hourly_rate = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    time_entries = db.relationship('TimeEntry', backref='customer', lazy=True, cascade='all, delete-orphan')
    projects = db.relationship('Project', backref='customer', lazy=True, cascade='all, delete-orphan')
    invoices = db.relationship('Invoice', backref='customer', lazy=True, cascade='all, delete-orphan')


class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, unique=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    hourly_rate = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    time_entries = db.relationship('TimeEntry', backref='employee', lazy=True, cascade='all, delete-orphan')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Service(db.Model):
    __tablename__ = 'services'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text)
    billable_rate = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    time_entries = db.relationship('TimeEntry', backref='service', lazy=True)


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    project_number = db.Column(db.String(50), unique=True)
    status = db.Column(db.String(50), default='in_progress')  # in_progress, completed, on_hold
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    time_entries = db.relationship('TimeEntry', backref='project', lazy=True, cascade='all, delete-orphan')
    invoices = db.relationship('Invoice', backref='project', lazy=True, cascade='all, delete-orphan')


class TimeEntry(db.Model):
    __tablename__ = 'time_entries'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'))

    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    break_minutes = db.Column(db.Integer, default=0)

    billable = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text)
    cost_code = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def duration_hours(self):
        delta = self.end_time - self.start_time
        total_seconds = delta.total_seconds()
        break_seconds = self.break_minutes * 60
        billable_seconds = total_seconds - break_seconds
        return billable_seconds / 3600

    @property
    def total_hours(self):
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 3600


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))

    invoice_number = db.Column(db.String(50), unique=True)
    invoice_date = db.Column(db.DateTime, default=datetime.utcnow)
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)

    total_hours = db.Column(db.Float, default=0.0)
    hourly_rate = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)

    status = db.Column(db.String(50), default='draft')  # draft, sent, paid, overdue
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    line_items = db.relationship('InvoiceLineItem', backref='invoice', lazy=True, cascade='all, delete-orphan')


class InvoiceLineItem(db.Model):
    __tablename__ = 'invoice_line_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    time_entry_id = db.Column(db.Integer, db.ForeignKey('time_entries.id'))

    description = db.Column(db.String(255), nullable=False)
    hours = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
