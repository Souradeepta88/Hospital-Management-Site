from flask import Flask, render_template, request, redirect, flash
from allinone import DB

app = Flask(__name__)
app.secret_key = "silvercare_secret_2026"


@app.route("/")
def hello_world():
    tt = ['/', '/about', '/costs', '/contact', '/database',
          '/userform', '/userdisplay',
          '/doctorform', '/doctordisplay',
          '/patientform', '/patientdisplay',
          '/patienthistoryform', '/patienthistorydisplay',
          '/prescriptionform', '/prescriptiondisplay',
          '/medicationform', '/medicationdisplay',
          '/costsform', '/costsdisplay']
    return render_template("index.jinja2.html", tt=tt)


@app.route("/about")
def about():
    return render_template("about.jinja2.html")


@app.route("/costs")
def costs():
    stats = {
        "total_admission_cost": 0, "total_medicine_cost": 0,
        "total_doctor_fee": 0,    "grand_total": 0,
        "total_patients": 0,      "admitted_count": 0,
        "outpatient_count": 0,    "avg_bill": 0,
        "highest_bill": 0,        "lowest_bill": 0,
    }
    try:
        rows = DB().select("""
            SELECT
                COUNT(*)                                              AS total_patients,
                COALESCE(SUM(admission_cost), 0)                     AS total_admission_cost,
                COALESCE(SUM(medicine_cost), 0)                      AS total_medicine_cost,
                COALESCE(SUM(doctor_fee), 0)                         AS total_doctor_fee,
                COALESCE(SUM(admission_cost+medicine_cost+doctor_fee),0) AS grand_total,
                COUNT(*) FILTER (WHERE admitted = true)              AS admitted_count,
                COUNT(*) FILTER (WHERE admitted = false)             AS outpatient_count,
                COALESCE(AVG(admission_cost+medicine_cost+doctor_fee),0) AS avg_bill,
                COALESCE(MAX(admission_cost+medicine_cost+doctor_fee),0) AS highest_bill,
                COALESCE(MIN(admission_cost+medicine_cost+doctor_fee),0) AS lowest_bill
            FROM costs;
        """)
        if rows:
            r = rows[0]
            stats["total_patients"]       = int(r[0])
            stats["total_admission_cost"] = int(r[1])
            stats["total_medicine_cost"]  = int(r[2])
            stats["total_doctor_fee"]     = int(r[3])
            stats["grand_total"]          = int(r[4])
            stats["admitted_count"]       = int(r[5])
            stats["outpatient_count"]     = int(r[6])
            stats["avg_bill"]             = round(float(r[7]), 2)
            stats["highest_bill"]         = int(r[8])
            stats["lowest_bill"]          = int(r[9])
    except Exception:
        pass
    return render_template("costs.jinja2.html", stats=stats)


@app.route("/contact")
def contact():
    return render_template("contact.jinja2.html")


@app.route("/database")
def database():
    tables = {}
    table_queries = {
        "users": "SELECT * FROM users;",
        "doctor": "SELECT * FROM doctor;",
        "patients": "SELECT * FROM patients;",
        "patienthistory": "SELECT * FROM patienthistory;",
        "prescription": "SELECT * FROM prescription;",
        "medication": "SELECT * FROM medication;",
        "costs": "SELECT * FROM costs;",
    }
    for table_name, query in table_queries.items():
        try:
            tables[table_name] = DB().select(query)
        except Exception:
            tables[table_name] = []
    return render_template("database.jinja2.html", tables=tables)


# ════════════════════════════════════════════════════════════════
#  TO-DO SECTION  ──  Queries / Trigger / Procedure
# ════════════════════════════════════════════════════════════════

@app.route("/s1")
def s1():
    data  = []
    error = None
    try:
        data = DB().select("""
            SELECT id, username, qualification, specialization
            FROM doctor
            WHERE specialization = 'Cardiology'
              AND IsActive = true;
        """)
    except Exception as e:
        error = str(e)
    return render_template("s1.jinja2.html", data=data, error=error)


@app.route("/c1")
def c1():
    data  = []
    error = None
    try:
        data = DB().select("""
            SELECT
                p.id,
                p.username,
                COUNT(ph.id)       AS total_visits,
                SUM(ph.BillAmount) AS total_spent
            FROM patients p
            JOIN patienthistory ph ON p.username = ph.patient_name
            GROUP BY p.id, p.username
            HAVING COUNT(ph.id) > 0
            ORDER BY total_spent DESC;
        """)
    except Exception as e:
        error = str(e)
    return render_template("c1.jinja2.html", data=data, error=error)


@app.route("/c2")
def c2():
    data  = []
    error = None
    try:
        data = DB().select("""
            SELECT
                p.username     AS patient_name,
                d.username     AS doctor_name,
                m.medication,
                pr.visit_date
            FROM patients p
            JOIN prescription pr ON p.username  = pr.patient_name
            JOIN doctor d        ON pr.doctor_name = d.username
            JOIN medication m    ON pr.prescription_number = m.prescription_number
            WHERE m.medication = 'Amoxicillin'
            ORDER BY pr.visit_date DESC;
        """)
    except Exception as e:
        error = str(e)
    return render_template("c2.jinja2.html", data=data, error=error)


@app.route("/t1", methods=["GET", "POST"])
def t1():
    message   = None
    error     = None
    sql_shown = """\
CREATE OR REPLACE FUNCTION fn_patienthistory_defaults()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.visit_date IS NULL THEN
        NEW.visit_date := CURRENT_DATE;
    END IF;
    IF NEW.BillAmount < 0 THEN
        RAISE EXCEPTION 'BillAmount cannot be negative (got %)', NEW.BillAmount;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_patienthistory_defaults ON patienthistory;

CREATE TRIGGER trg_patienthistory_defaults
BEFORE INSERT ON patienthistory
FOR EACH ROW
EXECUTE FUNCTION fn_patienthistory_defaults();"""

    if request.method == "POST":
        try:
            DB().insert("""
                CREATE OR REPLACE FUNCTION fn_patienthistory_defaults()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF NEW.visit_date IS NULL THEN
                        NEW.visit_date := CURRENT_DATE;
                    END IF;
                    IF NEW.BillAmount < 0 THEN
                        RAISE EXCEPTION 'BillAmount cannot be negative (got %)', NEW.BillAmount;
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)
            DB().insert("DROP TRIGGER IF EXISTS trg_patienthistory_defaults ON patienthistory;")
            DB().insert("""
                CREATE TRIGGER trg_patienthistory_defaults
                BEFORE INSERT ON patienthistory
                FOR EACH ROW
                EXECUTE FUNCTION fn_patienthistory_defaults();
            """)
            message = "Trigger installed successfully on patienthistory."
        except Exception as e:
            error = str(e)

    return render_template("t1.jinja2.html",
                           sql_shown=sql_shown,
                           message=message,
                           error=error)


@app.route("/p1", methods=["GET", "POST"])
def p1():
    message   = None
    error     = None
    doctor_id = None
    sql_shown = """\
CREATE OR REPLACE PROCEDURE deactivate_doctor(p_doctor_id INT)
LANGUAGE plpgsql AS $$
DECLARE
    rows_affected INT;
BEGIN
    UPDATE doctor
    SET    IsActive = false
    WHERE  id = p_doctor_id;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;

    IF rows_affected > 0 THEN
        RAISE NOTICE 'Doctor ID % has been deactivated.', p_doctor_id;
    ELSE
        RAISE NOTICE 'Doctor ID % not found.', p_doctor_id;
    END IF;
END;
$$;

CALL deactivate_doctor(101);"""

    if request.method == "POST":
        doctor_id = request.form.get("doctor_id", "").strip()
        if not doctor_id.isdigit():
            error = "Please enter a valid numeric Doctor ID."
        else:
            try:
                rows = DB().select(f"""
                    SELECT id, username FROM doctor WHERE id = {int(doctor_id)};
                """)
                if not rows:
                    error = f"Doctor with ID {doctor_id} not found in the database."
                else:
                    DB().insert(f"""
                        UPDATE doctor
                        SET IsActive = false
                        WHERE id = {int(doctor_id)};
                    """)
                    message = (f"Doctor '{rows[0][1]}' (ID {doctor_id}) "
                               f"has been successfully deactivated.")
            except Exception as e:
                error = str(e)

    return render_template("p1.jinja2.html",
                           sql_shown=sql_shown,
                           message=message,
                           error=error,
                           doctor_id=doctor_id)


# ════════════════════════════════════════════════════════════════
#  EXISTING ROUTES  ──  with FK pre-checks
# ════════════════════════════════════════════════════════════════

@app.route("/userform", methods=["GET", "POST"])
def userform():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        DB().insert("""
        CREATE TABLE IF NOT EXISTS users(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            username VARCHAR(50) UNIQUE,
            password VARCHAR(100)
        );""")
        DB().insert(f"INSERT INTO users (username, password) VALUES ('{username}', '{password}');")
        return redirect("/userdisplay")
    return render_template("userform.jinja2.html")


# ── FK-1 : doctor.username → users.username ───────────────────
@app.route("/doctorform", methods=["GET", "POST"])
def doctorform():
    if request.method == "POST":
        username       = request.form.get("username")
        qualification  = request.form.get("qualification")
        phone          = request.form.get("phone")
        email          = request.form.get("email")
        time           = request.form.get("time")
        age            = request.form.get("age")
        specialization = request.form.get("specialization")
        IsActive       = True if request.form.get("IsActive") == "true" else False

        # FK-1 pre-check: username must exist in users
        try:
            existing = DB().select(f"SELECT username FROM users WHERE username = '{username}';")
        except Exception:
            existing = []

        if not existing:
            return render_template(
                "error1.jinja2.html",
                missing_value=username,
                child_table="doctor",
                child_column="username",
                parent_table="users",
                parent_column="username",
                fix_url="/userform"
            )

        DB().insert("""
        CREATE TABLE IF NOT EXISTS doctor(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            username VARCHAR(50) UNIQUE,
            qualification VARCHAR(100),
            phone VARCHAR(20),
            email VARCHAR(100) CHECK (email LIKE '%@%.%'),
            time TIME, age INT, specialization VARCHAR(100),
            IsActive BOOLEAN CHECK (IsActive IN (true, false)),
            CONSTRAINT fk_doctor_user FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        );""")
        DB().insert(f"""
        INSERT INTO doctor(username, qualification, phone, email, time, age, specialization, IsActive)
        VALUES ('{username}','{qualification}','{phone}','{email}','{time}',{age},'{specialization}',{IsActive});""")
        return redirect("/doctordisplay")
    return render_template("doctorform.jinja2.html")


@app.route("/userdisplay")
def userdisplay():
    data = DB().select("SELECT * FROM users;")
    return render_template("userdisplay.jinja2.html", data=data)


@app.route("/doctordisplay")
def doctordisplay():
    data = DB().select("SELECT * FROM doctor;")
    return render_template("doctordisplay.jinja2.html", data=data)


# ── FK-2 : patients.username → users.username ─────────────────
@app.route("/patientform", methods=["GET", "POST"])
def patientform():
    if request.method == "POST":
        username     = request.form.get("username")
        phone        = request.form.get("phone")
        email        = request.form.get("email")
        address      = request.form.get("address")
        age          = request.form.get("age")
        registerdate = request.form.get("registerdate")

        # FK-2 pre-check: username must exist in users
        try:
            existing = DB().select(f"SELECT username FROM users WHERE username = '{username}';")
        except Exception:
            existing = []

        if not existing:
            return render_template(
                "error2.jinja2.html",
                missing_value=username,
                child_table="patients",
                child_column="username",
                parent_table="users",
                parent_column="username",
                fix_url="/userform"
            )

        DB().insert("""
        CREATE TABLE IF NOT EXISTS patients(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            username VARCHAR(50) UNIQUE, phone VARCHAR(20),
            email VARCHAR(100) CHECK (email LIKE '%@%.%'),
            address VARCHAR(200), age INT, registerdate DATE,
            CONSTRAINT fk_patient_user FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        );""")
        DB().insert(f"""
        INSERT INTO patients (username, phone, email, address, age, registerdate)
        VALUES ('{username}','{phone}','{email}','{address}',{age},'{registerdate}');""")
        return redirect("/patientdisplay")
    return render_template("patientform.jinja2.html")


@app.route("/patientdisplay")
def patientdisplay():
    data = DB().select("SELECT * FROM patients;")
    return render_template("patientdisplay.jinja2.html", data=data)


# ── FK-3 : patienthistory.patient_name → patients.username
# ── FK-4 : patienthistory.doctor_name  → doctor.username
@app.route("/patienthistoryform", methods=["GET", "POST"])
def patienthistoryform():
    if request.method == "POST":
        patient_name = request.form.get("patient_name")
        doctor_name  = request.form.get("doctor_name")
        visit_date   = request.form.get("visit_date")
        treatment    = request.form.get("treatment")
        description  = request.form.get("description")
        BillAmount   = request.form.get("BillAmount")

        # FK-3 pre-check: patient_name must exist in patients
        try:
            existing_patient = DB().select(f"SELECT username FROM patients WHERE username = '{patient_name}';")
        except Exception:
            existing_patient = []

        if not existing_patient:
            return render_template(
                "error3.jinja2.html",
                missing_value=patient_name,
                child_table="patienthistory",
                child_column="patient_name",
                parent_table="patients",
                parent_column="username",
                fix_url="/patientform"
            )

        # FK-4 pre-check: doctor_name must exist in doctor
        try:
            existing_doctor = DB().select(f"SELECT username FROM doctor WHERE username = '{doctor_name}';")
        except Exception:
            existing_doctor = []

        if not existing_doctor:
            return render_template(
                "error4.jinja2.html",
                missing_value=doctor_name,
                child_table="patienthistory",
                child_column="doctor_name",
                parent_table="doctor",
                parent_column="username",
                fix_url="/doctorform"
            )

        DB().insert("""
        CREATE TABLE IF NOT EXISTS patienthistory(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            patient_name VARCHAR(50), doctor_name VARCHAR(50), visit_date DATE,
            treatment VARCHAR(200), description VARCHAR(500), BillAmount INT,
            CONSTRAINT fk_history_patient FOREIGN KEY (patient_name) REFERENCES patients(username) ON DELETE CASCADE,
            CONSTRAINT fk_history_doctor  FOREIGN KEY (doctor_name)  REFERENCES doctor(username)   ON DELETE CASCADE
        );""")
        DB().insert(f"""
        INSERT INTO patienthistory (patient_name,doctor_name,visit_date,treatment,description,BillAmount)
        VALUES ('{patient_name}','{doctor_name}','{visit_date}','{treatment}','{description}',{BillAmount});""")
        return redirect("/patienthistorydisplay")
    return render_template("patienthistoryform.jinja2.html")


@app.route("/patienthistorydisplay")
def patienthistorydisplay():
    data = DB().select("SELECT * FROM patienthistory;")
    return render_template("patienthistorydisplay.jinja2.html", data=data)


# ── FK-5 : prescription.patient_name → patients.username
# ── FK-6 : prescription.doctor_name  → doctor.username
@app.route("/prescriptionform", methods=["GET", "POST"])
def prescriptionform():
    if request.method == "POST":
        prescription_number = request.form.get("prescription_number")
        physical_id         = request.form.get("physical_id")
        patient_name        = request.form.get("patient_name")
        doctor_name         = request.form.get("doctor_name")
        visit_date          = request.form.get("visit_date")

        # FK-5 pre-check: patient_name must exist in patients
        try:
            existing_patient = DB().select(f"SELECT username FROM patients WHERE username = '{patient_name}';")
        except Exception:
            existing_patient = []

        if not existing_patient:
            return render_template(
                "error5.jinja2.html",
                missing_value=patient_name,
                child_table="prescription",
                child_column="patient_name",
                parent_table="patients",
                parent_column="username",
                fix_url="/patientform"
            )

        # FK-6 pre-check: doctor_name must exist in doctor
        try:
            existing_doctor = DB().select(f"SELECT username FROM doctor WHERE username = '{doctor_name}';")
        except Exception:
            existing_doctor = []

        if not existing_doctor:
            return render_template(
                "error6.jinja2.html",
                missing_value=doctor_name,
                child_table="prescription",
                child_column="doctor_name",
                parent_table="doctor",
                parent_column="username",
                fix_url="/doctorform"
            )

        DB().insert("""
        CREATE TABLE IF NOT EXISTS prescription(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            prescription_number VARCHAR(50) UNIQUE, physical_id VARCHAR(50),
            patient_name VARCHAR(50), doctor_name VARCHAR(50), visit_date DATE,
            CONSTRAINT fk_prescription_patient FOREIGN KEY (patient_name) REFERENCES patients(username) ON DELETE CASCADE,
            CONSTRAINT fk_prescription_doctor  FOREIGN KEY (doctor_name)  REFERENCES doctor(username)  ON DELETE CASCADE
        );""")
        DB().insert(f"""
        INSERT INTO prescription (prescription_number,physical_id,patient_name,doctor_name,visit_date)
        VALUES ('{prescription_number}','{physical_id}','{patient_name}','{doctor_name}','{visit_date}');""")
        return redirect("/prescriptiondisplay")
    return render_template("prescriptionform.jinja2.html")


@app.route("/prescriptiondisplay")
def prescriptiondisplay():
    data = DB().select("SELECT * FROM prescription;")
    return render_template("prescriptiondisplay.jinja2.html", data=data)


# ── FK-7 : medication.prescription_number → prescription.prescription_number
@app.route("/medicationform", methods=["GET", "POST"])
def medicationform():
    if request.method == "POST":
        prescription_number = request.form.get("prescription_number")
        medication          = request.form.get("medication")
        dosage              = request.form.get("dosage")

        # FK-7 pre-check: prescription_number must exist in prescription
        try:
            existing_rx = DB().select(
                f"SELECT prescription_number FROM prescription WHERE prescription_number = '{prescription_number}';"
            )
        except Exception:
            existing_rx = []

        if not existing_rx:
            return render_template(
                "error7.jinja2.html",
                missing_value=prescription_number,
                child_table="medication",
                child_column="prescription_number",
                parent_table="prescription",
                parent_column="prescription_number",
                fix_url="/prescriptionform"
            )

        DB().insert("""
        CREATE TABLE IF NOT EXISTS medication(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            prescription_number VARCHAR(50), medication VARCHAR(100), dosage VARCHAR(100),
            CONSTRAINT fk_medication_prescription
                FOREIGN KEY (prescription_number) REFERENCES prescription(prescription_number) ON DELETE CASCADE
        );""")
        DB().insert(f"""
        INSERT INTO medication (prescription_number,medication,dosage)
        VALUES ('{prescription_number}','{medication}','{dosage}');""")
        return redirect("/medicationdisplay")
    return render_template("medicationform.jinja2.html")


@app.route("/medicationdisplay")
def medicationdisplay():
    data = DB().select("SELECT * FROM medication;")
    return render_template("medicationdisplay.jinja2.html", data=data)


# ── FK-8 : costs.patient_name → patients.username ─────────────
@app.route("/costsform", methods=["GET", "POST"])
def costsform():
    if request.method == "POST":
        patient_name   = request.form.get("patient_name")
        admitted       = request.form.get("admitted")
        admission_cost = request.form.get("admission_cost")
        medicine_cost  = request.form.get("medicine_cost")
        doctor_fee     = request.form.get("doctor_fee")
        admitted       = True if admitted == "true" else False

        # FK-8 pre-check: patient_name must exist in patients
        try:
            existing_patient = DB().select(f"SELECT username FROM patients WHERE username = '{patient_name}';")
        except Exception:
            existing_patient = []

        if not existing_patient:
            return render_template(
                "error8.jinja2.html",
                missing_value=patient_name,
                child_table="costs",
                child_column="patient_name",
                parent_table="patients",
                parent_column="username",
                fix_url="/patientform"
            )

        DB().insert("""
        CREATE TABLE IF NOT EXISTS costs(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            patient_name VARCHAR(50),
            admitted BOOLEAN CHECK (admitted IN (true, false)),
            admission_cost INT, medicine_cost INT, doctor_fee INT,
            CONSTRAINT chk_admission_cost CHECK (
                (admitted = true  AND admission_cost IS NOT NULL) OR
                (admitted = false AND admission_cost = 0)
            ),
            CONSTRAINT fk_costs_patient FOREIGN KEY (patient_name) REFERENCES patients(username) ON DELETE CASCADE
        );""")
        DB().insert(f"""
        INSERT INTO costs (patient_name,admitted,admission_cost,medicine_cost,doctor_fee)
        VALUES ('{patient_name}',{admitted},{admission_cost},{medicine_cost},{doctor_fee});""")
        return redirect("/costsdisplay")
    return render_template("costsform.jinja2.html")


@app.route("/costsdisplay")
def costsdisplay():
    data = DB().select("SELECT * FROM costs;")
    return render_template("costsdisplay.jinja2.html", data=data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)