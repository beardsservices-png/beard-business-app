"""
Script to seed the database with historical time entry data from CSV
"""
import csv
from datetime import datetime
from app import create_app
from models import db, Customer, Employee, Service, Project, TimeEntry


def parse_time(time_str):
    """Parse time string from BusyBusy format"""
    if not time_str:
        return None
    try:
        # Handle ISO format with timezone: 2024-01-01T08:45:00.000-05:00
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    except:
        return None


def parse_hours(time_str):
    """Parse duration from HH:MM format"""
    if not time_str:
        return 0
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    return hours + minutes / 60


def load_csv_data(csv_file):
    """Load time entry data from CSV"""
    app = create_app()

    with app.app_context():
        employees_cache = {}
        customers_cache = {}
        projects_cache = {}

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for idx, row in enumerate(reader, 1):
                try:
                    # Parse employee
                    emp_id = row.get('Employee ID')
                    emp_key = emp_id
                    if emp_key not in employees_cache:
                        employee = Employee.query.filter_by(employee_id=int(emp_id)).first()
                        if not employee:
                            employee = Employee(
                                employee_id=int(emp_id),
                                first_name=row.get('First Name', 'Unknown'),
                                last_name=row.get('Last Name', 'Unknown'),
                                hourly_rate=50.0  # Default rate
                            )
                            db.session.add(employee)
                            db.session.flush()
                        employees_cache[emp_key] = employee

                    employee = employees_cache[emp_key]

                    # Parse customer
                    cust_name = row.get('Customer', '').strip()
                    if cust_name and cust_name not in customers_cache:
                        customer = Customer.query.filter_by(name=cust_name).first()
                        if not customer:
                            customer = Customer(
                                name=cust_name,
                                customer_type='residential',
                                hourly_rate=50.0  # Default rate
                            )
                            db.session.add(customer)
                            db.session.flush()
                        customers_cache[cust_name] = customer

                    customer = customers_cache.get(cust_name)

                    if not customer:
                        continue  # Skip if no customer

                    # Parse project
                    proj_name = row.get('Project', '').strip()
                    proj_num = row.get('Project #', '').strip()
                    proj_key = f"{cust_name}_{proj_name}" if proj_name else cust_name

                    if proj_key not in projects_cache and proj_name:
                        project = Project.query.filter_by(name=proj_name, customer_id=customer.id).first()
                        if not project:
                            project = Project(
                                customer_id=customer.id,
                                name=proj_name,
                                project_number=proj_num if proj_num else None,
                                status='completed'
                            )
                            db.session.add(project)
                            db.session.flush()
                        projects_cache[proj_key] = project

                    project = projects_cache.get(proj_key)

                    # Parse times
                    start_time = parse_time(row.get('Start'))
                    end_time = parse_time(row.get('End'))

                    if not start_time or not end_time:
                        continue

                    break_minutes = int(row.get('Break Total', '00:00').split(':')[0]) * 60 + \
                                    int(row.get('Break Total', '00:00').split(':')[1])

                    # Determine if billable
                    cost_code = row.get('Cost Code Desc.', '').lower()
                    billable = 'billable' in cost_code and 'non' not in cost_code.lower()

                    # Create time entry
                    time_entry = TimeEntry(
                        employee_id=employee.id,
                        customer_id=customer.id,
                        project_id=project.id if project else None,
                        start_time=start_time,
                        end_time=end_time,
                        break_minutes=break_minutes,
                        billable=billable,
                        description=row.get('Description', ''),
                        cost_code=row.get('Cost Code', '')
                    )
                    db.session.add(time_entry)

                except Exception as e:
                    print(f"Error on row {idx}: {e}")
                    continue

            # Commit all changes
            try:
                db.session.commit()
                print(f"✓ Successfully loaded time entry data")
                print(f"  - Employees: {len(employees_cache)}")
                print(f"  - Customers: {len(customers_cache)}")
                print(f"  - Projects: {len(projects_cache)}")
            except Exception as e:
                db.session.rollback()
                print(f"✗ Error committing to database: {e}")


if __name__ == '__main__':
    import sys
    csv_file = sys.argv[1] if len(sys.argv) > 1 else '../data/time_entries.csv'
    load_csv_data(csv_file)
