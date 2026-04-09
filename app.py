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
#  TO-DO SECTION  ──  BATCH 1  (S1, C1, C2, T1, P1, CR1)
# ════════════════════════════════════════════════════════════════

@app.route("/s1")
def s1():
    data, error = [], None
    try:
        data = DB().select("""
            SELECT id, username, qualification, specialization
            FROM doctor
            WHERE specialization = 'Cardiology' AND IsActive = true;
        """)
    except Exception as e:
        error = str(e)
    return render_template("s1.jinja2.html", data=data, error=error)


@app.route("/c1")
def c1():
    data, error = [], None
    try:
        data = DB().select("""
            SELECT p.id, p.username,
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
    data, error = [], None
    try:
        data = DB().select("""
            SELECT p.username AS patient_name, d.username AS doctor_name,
                   m.medication, pr.visit_date
            FROM patients p
            JOIN prescription pr ON p.username     = pr.patient_name
            JOIN doctor d        ON pr.doctor_name  = d.username
            JOIN medication m    ON pr.prescription_number = m.prescription_number
            WHERE m.medication = 'Amoxicillin'
            ORDER BY pr.visit_date DESC;
        """)
    except Exception as e:
        error = str(e)
    return render_template("c2.jinja2.html", data=data, error=error)


def _check_trigger_status():
    """Returns True if trg_patienthistory_defaults trigger currently exists."""
    try:
        rows = DB().select("""
            SELECT 1
            FROM information_schema.triggers
            WHERE trigger_name = 'trg_patienthistory_defaults'
              AND event_object_table = 'patienthistory';
        """)
        return bool(rows)
    except Exception:
        return False


@app.route("/t1", methods=["GET", "POST"])
def t1():
    message, error = None, None
    action = request.form.get("action") if request.method == "POST" else None

    deploy_sql = """\
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

    undeploy_sql = """\
DROP TRIGGER IF EXISTS trg_patienthistory_defaults ON patienthistory;

DROP FUNCTION IF EXISTS fn_patienthistory_defaults();"""

    if request.method == "POST":
        if action == "deploy":
            try:
                DB().insert("""
                    CREATE TABLE IF NOT EXISTS patienthistory(
                        id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        patient_name VARCHAR(50), doctor_name VARCHAR(50), visit_date DATE,
                        treatment VARCHAR(200), description VARCHAR(500), BillAmount INT,
                        CONSTRAINT fk_history_patient FOREIGN KEY (patient_name) REFERENCES patients(username) ON DELETE CASCADE,
                        CONSTRAINT fk_history_doctor  FOREIGN KEY (doctor_name)  REFERENCES doctor(username)  ON DELETE CASCADE
                    );""")
                DB().insert("""
                    CREATE OR REPLACE FUNCTION fn_patienthistory_defaults()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        IF NEW.visit_date IS NULL THEN NEW.visit_date := CURRENT_DATE; END IF;
                        IF NEW.BillAmount < 0 THEN
                            RAISE EXCEPTION 'BillAmount cannot be negative (got %)', NEW.BillAmount;
                        END IF;
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;""")
                DB().insert("DROP TRIGGER IF EXISTS trg_patienthistory_defaults ON patienthistory;")
                DB().insert("""
                    CREATE TRIGGER trg_patienthistory_defaults
                    BEFORE INSERT ON patienthistory
                    FOR EACH ROW
                    EXECUTE FUNCTION fn_patienthistory_defaults();""")
                message = ("deploy_ok", "Trigger installed successfully on patienthistory.")
            except Exception as e:
                error = ("deploy", str(e))

        elif action == "undeploy":
            try:
                DB().insert("DROP TRIGGER IF EXISTS trg_patienthistory_defaults ON patienthistory;")
                DB().insert("DROP FUNCTION IF EXISTS fn_patienthistory_defaults();")
                message = ("undeploy_ok", "Trigger and function removed successfully from the database.")
            except Exception as e:
                error = ("undeploy", str(e))

    trigger_active = _check_trigger_status()

    return render_template(
        "t1.jinja2.html",
        deploy_sql=deploy_sql,
        undeploy_sql=undeploy_sql,
        message=message,
        error=error,
        trigger_active=trigger_active,
    )


@app.route("/p1", methods=["GET", "POST"])
def p1():
    message, error, doctor_id = None, None, None
    sql_shown = """\
CREATE OR REPLACE PROCEDURE deactivate_doctor(p_doctor_id INT)
LANGUAGE plpgsql AS $$
DECLARE rows_affected INT;
BEGIN
    UPDATE doctor SET IsActive = false WHERE id = p_doctor_id;
    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    IF rows_affected > 0 THEN
        RAISE NOTICE 'Doctor ID % has been deactivated.', p_doctor_id;
    ELSE
        RAISE NOTICE 'Doctor ID % not found.', p_doctor_id;
    END IF;
END; $$;

CALL deactivate_doctor(101);"""

    if request.method == "POST":
        doctor_id = request.form.get("doctor_id", "").strip()
        if not doctor_id.isdigit():
            error = "Please enter a valid numeric Doctor ID."
        else:
            try:
                rows = DB().select(f"SELECT id, username FROM doctor WHERE id = {int(doctor_id)};")
                if not rows:
                    error = f"Doctor with ID {doctor_id} not found."
                else:
                    DB().insert(f"UPDATE doctor SET IsActive = false WHERE id = {int(doctor_id)};")
                    message = f"Doctor '{rows[0][1]}' (ID {doctor_id}) has been successfully deactivated."
            except Exception as e:
                error = str(e)
    return render_template("p1.jinja2.html", sql_shown=sql_shown,
                           message=message, error=error, doctor_id=doctor_id)


@app.route("/cr1", methods=["GET", "POST"])
def cr1():
    """Cursor 1 — Doctors whose average patient age exceeds a given threshold."""
    data, error = [], None
    p_age = None
    sql_shown = """\
-- Oracle original (adapted to PostgreSQL):
-- PROCEDURE doctors_avg_patient_age(p_age NUMBER)
-- CURSOR c_doc IS
--     SELECT ph.doctor_name, ROUND(AVG(p.age), 2) AS avg_age
--     FROM patienthistory ph
--     JOIN patients p ON ph.patient_name = p.username
--     GROUP BY ph.doctor_name
--     HAVING AVG(p.age) > p_age
--     ORDER BY avg_age DESC;

SELECT
    ph.doctor_name,
    ROUND(AVG(p.age), 2) AS avg_age
FROM patienthistory ph
JOIN patients p ON ph.patient_name = p.username
GROUP BY ph.doctor_name
HAVING AVG(p.age) > :p_age
ORDER BY avg_age DESC;"""

    default_age = 30

    if request.method == "POST":
        age_input = request.form.get("p_age", "").strip()
        try:
            p_age = int(age_input)
        except (ValueError, TypeError):
            error = "Please enter a valid integer age threshold."
            p_age = default_age
    else:
        p_age = default_age

    if error is None:
        try:
            data = DB().select(f"""
                SELECT
                    ph.doctor_name,
                    ROUND(AVG(p.age), 2) AS avg_age
                FROM patienthistory ph
                JOIN patients p ON ph.patient_name = p.username
                GROUP BY ph.doctor_name
                HAVING AVG(p.age) > {int(p_age)}
                ORDER BY avg_age DESC;
            """)
        except Exception as e:
            error = str(e)

    return render_template("cr1.jinja2.html",
                           data=data, error=error,
                           p_age=p_age, sql_shown=sql_shown)


# ════════════════════════════════════════════════════════════════
#  TO-DO SECTION  ──  BATCH 2  (S2, C3, C4, T2, T3, T4, P2, CR2)
# ════════════════════════════════════════════════════════════════

@app.route("/s2")
def s2():
    data, error = [], None
    try:
        data = DB().select("""
            SELECT patient_name, medicine_cost
            FROM costs
            WHERE medicine_cost > 1000
            ORDER BY medicine_cost DESC;
        """)
    except Exception as e:
        error = str(e)
    return render_template("s2.jinja2.html", data=data, error=error)


@app.route("/c3")
def c3():
    data, error = [], None
    try:
        data = DB().select("""
            SELECT
                ph.patient_name,
                COUNT(ph.id) AS total_visits,
                COALESCE(
                    (SELECT SUM(c.medicine_cost + c.doctor_fee + COALESCE(c.admission_cost, 0))
                     FROM costs c
                     WHERE c.patient_name = ph.patient_name),
                0) AS total_spent
            FROM patienthistory ph
            GROUP BY ph.patient_name
            ORDER BY total_visits DESC
            LIMIT 10;
        """)
    except Exception as e:
        error = str(e)
    return render_template("c3.jinja2.html", data=data, error=error)


@app.route("/c4")
def c4():
    data, error = [], None
    try:
        data = DB().select("""
            SELECT
                d.username                                          AS doctor_name,
                COUNT(ph.id)                                        AS total_visits,
                COUNT(DISTINCT ph.patient_name)                     AS unique_patients,
                ROUND(
                    COUNT(ph.id)::NUMERIC /
                    NULLIF(COUNT(DISTINCT ph.patient_name), 0),
                2)                                                  AS avg_visits_per_patient
            FROM doctor d
            LEFT JOIN patienthistory ph ON d.username = ph.doctor_name
            GROUP BY d.username
            ORDER BY total_visits DESC;
        """)
    except Exception as e:
        error = str(e)
    return render_template("c4.jinja2.html", data=data, error=error)


@app.route("/t2")
def t2():
    data, error = [], None
    try:
        data = DB().select("""
            SELECT
                ph.patient_name,
                ph.doctor_name,
                COUNT(ph.id) AS visit_count
            FROM patienthistory ph
            GROUP BY ph.patient_name, ph.doctor_name
            HAVING COUNT(ph.id) >= 2
            ORDER BY visit_count DESC;
        """)
    except Exception as e:
        error = str(e)
    return render_template("t2.jinja2.html", data=data, error=error)


# ── T3 ── Trigger: update total_cost in patient after cost insert ─────────────

def _check_t3_trigger_status():
    """Returns True if trg_update_total_cost trigger currently exists."""
    try:
        rows = DB().select("""
            SELECT 1
            FROM information_schema.triggers
            WHERE trigger_name = 'trg_update_total_cost'
              AND event_object_table = 'cost';
        """)
        return bool(rows)
    except Exception:
        return False


@app.route("/t3", methods=["GET", "POST"])
def t3():
    message, error = None, None
    action = request.form.get("action") if request.method == "POST" else None

    deploy_sql = """\
CREATE OR REPLACE FUNCTION update_total_cost()
RETURNS TRIGGER AS $$
BEGIN
    -- Update total cost in patient table
    UPDATE patient
    SET total_cost = COALESCE(total_cost, 0) + NEW.amount
    WHERE patient_id = NEW.patient_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_total_cost ON cost;

CREATE TRIGGER trg_update_total_cost
AFTER INSERT ON cost
FOR EACH ROW
EXECUTE FUNCTION update_total_cost();"""

    undeploy_sql = """\
DROP TRIGGER IF EXISTS trg_update_total_cost ON cost;

DROP FUNCTION IF EXISTS update_total_cost();"""

    if request.method == "POST":
        if action == "deploy":
            try:
                DB().insert("""
                    CREATE OR REPLACE FUNCTION update_total_cost()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        UPDATE patient
                        SET total_cost = COALESCE(total_cost, 0) + NEW.amount
                        WHERE patient_id = NEW.patient_id;
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;""")
                DB().insert("DROP TRIGGER IF EXISTS trg_update_total_cost ON cost;")
                DB().insert("""
                    CREATE TRIGGER trg_update_total_cost
                    AFTER INSERT ON cost
                    FOR EACH ROW
                    EXECUTE FUNCTION update_total_cost();""")
                message = ("deploy_ok", "Trigger trg_update_total_cost installed successfully on cost.")
            except Exception as e:
                error = ("deploy", str(e))

        elif action == "undeploy":
            try:
                DB().insert("DROP TRIGGER IF EXISTS trg_update_total_cost ON cost;")
                DB().insert("DROP FUNCTION IF EXISTS update_total_cost();")
                message = ("undeploy_ok", "Trigger and function removed successfully from the database.")
            except Exception as e:
                error = ("undeploy", str(e))

    trigger_active = _check_t3_trigger_status()

    return render_template(
        "t3.jinja2.html",
        deploy_sql=deploy_sql,
        undeploy_sql=undeploy_sql,
        message=message,
        error=error,
        trigger_active=trigger_active,
    )


# ── T4 ── Trigger: auto-classify treatment_type on patienthistory ─────────────

def _check_t4_trigger_status():
    """Returns True if trg_treatment_type trigger currently exists."""
    try:
        rows = DB().select("""
            SELECT 1
            FROM information_schema.triggers
            WHERE trigger_name = 'trg_treatment_type'
              AND event_object_table = 'patienthistory';
        """)
        return bool(rows)
    except Exception:
        return False


@app.route("/t4", methods=["GET", "POST"])
def t4():
    message, error = None, None
    action = request.form.get("action") if request.method == "POST" else None

    deploy_sql = """\
CREATE OR REPLACE FUNCTION fn_treatment_type()
RETURNS TRIGGER AS $$
BEGIN
    IF LOWER(NEW.treatment) LIKE '%cardio%' THEN
        NEW.treatment_type := 'Cardiology';
    ELSIF LOWER(NEW.treatment) LIKE '%neuro%' THEN
        NEW.treatment_type := 'Neurology';
    ELSIF LOWER(NEW.treatment) LIKE '%skin%'
       OR LOWER(NEW.treatment) LIKE '%derma%' THEN
        NEW.treatment_type := 'Dermatology';
    ELSIF LOWER(NEW.treatment) LIKE '%pediatric%' THEN
        NEW.treatment_type := 'Pediatrics';
    ELSIF LOWER(NEW.treatment) LIKE '%ortho%'
       OR LOWER(NEW.treatment) LIKE '%joint%' THEN
        NEW.treatment_type := 'Orthopedics';
    ELSE
        NEW.treatment_type := 'General';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_treatment_type ON patienthistory;

CREATE TRIGGER trg_treatment_type
BEFORE INSERT OR UPDATE ON patienthistory
FOR EACH ROW
EXECUTE FUNCTION fn_treatment_type();"""

    undeploy_sql = """\
DROP TRIGGER IF EXISTS trg_treatment_type ON patienthistory;

DROP FUNCTION IF EXISTS fn_treatment_type();"""

    if request.method == "POST":
        if action == "deploy":
            try:
                DB().insert("""
                    ALTER TABLE patienthistory
                    ADD COLUMN IF NOT EXISTS treatment_type VARCHAR(50);""")
                DB().insert("""
                    CREATE OR REPLACE FUNCTION fn_treatment_type()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        IF LOWER(NEW.treatment) LIKE '%cardio%' THEN
                            NEW.treatment_type := 'Cardiology';
                        ELSIF LOWER(NEW.treatment) LIKE '%neuro%' THEN
                            NEW.treatment_type := 'Neurology';
                        ELSIF LOWER(NEW.treatment) LIKE '%skin%'
                           OR LOWER(NEW.treatment) LIKE '%derma%' THEN
                            NEW.treatment_type := 'Dermatology';
                        ELSIF LOWER(NEW.treatment) LIKE '%pediatric%' THEN
                            NEW.treatment_type := 'Pediatrics';
                        ELSIF LOWER(NEW.treatment) LIKE '%ortho%'
                           OR LOWER(NEW.treatment) LIKE '%joint%' THEN
                            NEW.treatment_type := 'Orthopedics';
                        ELSE
                            NEW.treatment_type := 'General';
                        END IF;
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;""")
                DB().insert("DROP TRIGGER IF EXISTS trg_treatment_type ON patienthistory;")
                DB().insert("""
                    CREATE TRIGGER trg_treatment_type
                    BEFORE INSERT OR UPDATE ON patienthistory
                    FOR EACH ROW
                    EXECUTE FUNCTION fn_treatment_type();""")
                message = ("deploy_ok", "Trigger trg_treatment_type installed successfully on patienthistory.")
            except Exception as e:
                error = ("deploy", str(e))

        elif action == "undeploy":
            try:
                DB().insert("DROP TRIGGER IF EXISTS trg_treatment_type ON patienthistory;")
                DB().insert("DROP FUNCTION IF EXISTS fn_treatment_type();")
                message = ("undeploy_ok", "Trigger and function removed successfully from the database.")
            except Exception as e:
                error = ("undeploy", str(e))

    trigger_active = _check_t4_trigger_status()

    return render_template(
        "t4.jinja2.html",
        deploy_sql=deploy_sql,
        undeploy_sql=undeploy_sql,
        message=message,
        error=error,
        trigger_active=trigger_active,
    )


@app.route("/p2")
def p2():
    data, error = [], None
    sql_shown = """\
CREATE OR REPLACE PROCEDURE doctors_no_recent_visits()
LANGUAGE plpgsql AS $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN (
        SELECT d.username
        FROM   doctor d
        WHERE  NOT EXISTS (
            SELECT 1
            FROM   patienthistory ph
            WHERE  ph.doctor_name = d.username
              AND  ph.visit_date >= CURRENT_DATE - INTERVAL '12 months'
        )
    )
    LOOP
        RAISE NOTICE 'Doctor with No Recent Visits: %', rec.username;
    END LOOP;
END;
$$;

CALL doctors_no_recent_visits();"""

    try:
        data = DB().select("""
            SELECT
                d.id,
                d.username,
                d.specialization,
                d.qualification,
                d.isactive,
                MAX(ph.visit_date) AS last_visit
            FROM doctor d
            LEFT JOIN patienthistory ph ON d.username = ph.doctor_name
            GROUP BY d.id, d.username, d.specialization, d.qualification, d.isactive
            HAVING MAX(ph.visit_date) IS NULL
                OR MAX(ph.visit_date) < CURRENT_DATE - INTERVAL '12 months'
            ORDER BY last_visit ASC NULLS FIRST;
        """)
    except Exception as e:
        error = str(e)
    return render_template("p2.jinja2.html", data=data, error=error, sql_shown=sql_shown)


@app.route("/cr2")
def cr2():
    """Cursor 2 — Patients whose total costs across all records exceed ₹5,000."""
    data, error = [], None
    sql_shown = """\
-- Oracle original (adapted to PostgreSQL):
-- PROCEDURE high_cost_patients()
-- CURSOR c_pat IS
--     SELECT p.patient_name, SUM(c.amount) AS total_cost
--     FROM patient p
--     JOIN cost c ON p.patient_id = c.patient_id
--     GROUP BY p.patient_name
--     HAVING SUM(c.amount) > 2000;

SELECT
    c.patient_name,
    SUM(c.admission_cost + c.medicine_cost + c.doctor_fee) AS total_cost
FROM costs c
GROUP BY c.patient_name
HAVING SUM(c.admission_cost + c.medicine_cost + c.doctor_fee) > 2000
ORDER BY total_cost DESC;"""

    try:
        data = DB().select("""
            SELECT
                c.patient_name,
                SUM(c.admission_cost + c.medicine_cost + c.doctor_fee) AS total_cost
            FROM costs c
            GROUP BY c.patient_name
            HAVING SUM(c.admission_cost + c.medicine_cost + c.doctor_fee) > 2000
            ORDER BY total_cost DESC;
        """)
    except Exception as e:
        error = str(e)

    return render_template("cr2.jinja2.html", data=data, error=error, sql_shown=sql_shown)


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
            username VARCHAR(50) UNIQUE NOT NULL, password VARCHAR(100) NOT NULL
        );""")
        DB().insert(f"INSERT INTO users (username, password) VALUES ('{username}', '{password}');")
        return redirect("/userdisplay")
    return render_template("userform.jinja2.html")


@app.route("/doctorform", methods=["GET", "POST"])
def doctorform():
    if request.method == "POST":
        username=request.form.get("username"); qualification=request.form.get("qualification")
        phone=request.form.get("phone"); email=request.form.get("email")
        time=request.form.get("time"); age=request.form.get("age")
        specialization=request.form.get("specialization")
        IsActive = True if request.form.get("IsActive") == "true" else False
        try:
            existing = DB().select(f"SELECT username FROM users WHERE username = '{username}';")
        except Exception:
            existing = []
        if not existing:
            return render_template("error1.jinja2.html", missing_value=username,
                child_table="doctor", child_column="username",
                parent_table="users", parent_column="username", fix_url="/userform")
        DB().insert("""
        CREATE TABLE IF NOT EXISTS doctor(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            username VARCHAR(50) UNIQUE, qualification VARCHAR(100), phone VARCHAR(20),
            email VARCHAR(100) CHECK (email LIKE '%@%.%'), time TIME, age INT,
            specialization VARCHAR(100), IsActive BOOLEAN CHECK (IsActive IN (true, false)),
            CONSTRAINT fk_doctor_user FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        );""")
        DB().insert(f"""
        INSERT INTO doctor(username,qualification,phone,email,time,age,specialization,IsActive)
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


@app.route("/patientform", methods=["GET", "POST"])
def patientform():
    if request.method == "POST":
        username=request.form.get("username"); phone=request.form.get("phone")
        email=request.form.get("email"); address=request.form.get("address")
        age=request.form.get("age"); registerdate=request.form.get("registerdate")
        try:
            existing = DB().select(f"SELECT username FROM users WHERE username = '{username}';")
        except Exception:
            existing = []
        if not existing:
            return render_template("error2.jinja2.html", missing_value=username,
                child_table="patients", child_column="username",
                parent_table="users", parent_column="username", fix_url="/userform")
        DB().insert("""
        CREATE TABLE IF NOT EXISTS patients(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            username VARCHAR(50) UNIQUE, phone VARCHAR(20),
            email VARCHAR(100) CHECK (email LIKE '%@%.%'),
            address VARCHAR(200), age INT, registerdate DATE,
            CONSTRAINT fk_patient_user FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        );""")
        DB().insert(f"""
        INSERT INTO patients (username,phone,email,address,age,registerdate)
        VALUES ('{username}','{phone}','{email}','{address}',{age},'{registerdate}');""")
        return redirect("/patientdisplay")
    return render_template("patientform.jinja2.html")


@app.route("/patientdisplay")
def patientdisplay():
    data = DB().select("SELECT * FROM patients;")
    return render_template("patientdisplay.jinja2.html", data=data)


@app.route("/patienthistoryform", methods=["GET", "POST"])
def patienthistoryform():
    if request.method == "POST":
        patient_name=request.form.get("patient_name"); doctor_name=request.form.get("doctor_name")
        visit_date=request.form.get("visit_date"); treatment=request.form.get("treatment")
        description=request.form.get("description"); BillAmount=request.form.get("BillAmount")
        try:
            existing_patient = DB().select(f"SELECT username FROM patients WHERE username = '{patient_name}';")
        except Exception:
            existing_patient = []
        if not existing_patient:
            return render_template("error3.jinja2.html", missing_value=patient_name,
                child_table="patienthistory", child_column="patient_name",
                parent_table="patients", parent_column="username", fix_url="/patientform")
        try:
            existing_doctor = DB().select(f"SELECT username FROM doctor WHERE username = '{doctor_name}';")
        except Exception:
            existing_doctor = []
        if not existing_doctor:
            return render_template("error4.jinja2.html", missing_value=doctor_name,
                child_table="patienthistory", child_column="doctor_name",
                parent_table="doctor", parent_column="username", fix_url="/doctorform")
        try:
            bill_int = int(BillAmount)
        except (TypeError, ValueError):
            bill_int = 0
        if bill_int < 0:
            return render_template("patienthistoryform.jinja2.html",
                trigger_error="Bill Amount cannot be negative. The database trigger will block this insert.",
                form=request.form)
        visit_date_sql = f"'{visit_date}'" if visit_date and visit_date.strip() else "NULL"
        DB().insert("""
        CREATE TABLE IF NOT EXISTS patienthistory(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            patient_name VARCHAR(50), doctor_name VARCHAR(50), visit_date DATE,
            treatment VARCHAR(200), description VARCHAR(500), BillAmount INT,
            CONSTRAINT fk_history_patient FOREIGN KEY (patient_name) REFERENCES patients(username) ON DELETE CASCADE,
            CONSTRAINT fk_history_doctor  FOREIGN KEY (doctor_name)  REFERENCES doctor(username)  ON DELETE CASCADE
        );""")
        try:
            DB().insert(f"""
            INSERT INTO patienthistory (patient_name,doctor_name,visit_date,treatment,description,BillAmount)
            VALUES ('{patient_name}','{doctor_name}',{visit_date_sql},'{treatment}','{description}',{bill_int});""")
        except Exception as e:
            err_msg = str(e)
            if "BillAmount cannot be negative" in err_msg:
                err_msg = "Bill Amount cannot be negative — blocked by database trigger."
            return render_template("patienthistoryform.jinja2.html", trigger_error=err_msg, form=request.form)
        return redirect("/patienthistorydisplay")
    return render_template("patienthistoryform.jinja2.html", form=None)


@app.route("/patienthistorydisplay")
def patienthistorydisplay():
    data = DB().select("SELECT * FROM patienthistory;")
    return render_template("patienthistorydisplay.jinja2.html", data=data)


@app.route("/prescriptionform", methods=["GET", "POST"])
def prescriptionform():
    if request.method == "POST":
        prescription_number=request.form.get("prescription_number"); physical_id=request.form.get("physical_id")
        patient_name=request.form.get("patient_name"); doctor_name=request.form.get("doctor_name")
        visit_date=request.form.get("visit_date")
        try:
            existing_patient = DB().select(f"SELECT username FROM patients WHERE username = '{patient_name}';")
        except Exception:
            existing_patient = []
        if not existing_patient:
            return render_template("error5.jinja2.html", missing_value=patient_name,
                child_table="prescription", child_column="patient_name",
                parent_table="patients", parent_column="username", fix_url="/patientform")
        try:
            existing_doctor = DB().select(f"SELECT username FROM doctor WHERE username = '{doctor_name}';")
        except Exception:
            existing_doctor = []
        if not existing_doctor:
            return render_template("error6.jinja2.html", missing_value=doctor_name,
                child_table="prescription", child_column="doctor_name",
                parent_table="doctor", parent_column="username", fix_url="/doctorform")
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


@app.route("/medicationform", methods=["GET", "POST"])
def medicationform():
    if request.method == "POST":
        prescription_number=request.form.get("prescription_number")
        medication=request.form.get("medication"); dosage=request.form.get("dosage")
        try:
            existing_rx = DB().select(
                f"SELECT prescription_number FROM prescription WHERE prescription_number = '{prescription_number}';")
        except Exception:
            existing_rx = []
        if not existing_rx:
            return render_template("error7.jinja2.html", missing_value=prescription_number,
                child_table="medication", child_column="prescription_number",
                parent_table="prescription", parent_column="prescription_number", fix_url="/prescriptionform")
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


@app.route("/costsform", methods=["GET", "POST"])
def costsform():
    if request.method == "POST":
        patient_name=request.form.get("patient_name"); admitted=request.form.get("admitted")
        admission_cost=request.form.get("admission_cost"); medicine_cost=request.form.get("medicine_cost")
        doctor_fee=request.form.get("doctor_fee")
        admitted = True if admitted == "true" else False
        try:
            existing_patient = DB().select(f"SELECT username FROM patients WHERE username = '{patient_name}';")
        except Exception:
            existing_patient = []
        if not existing_patient:
            return render_template("error8.jinja2.html", missing_value=patient_name,
                child_table="costs", child_column="patient_name",
                parent_table="patients", parent_column="username", fix_url="/patientform")
        DB().insert("""
        CREATE TABLE IF NOT EXISTS costs(
            id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, patient_name VARCHAR(50),
            admitted BOOLEAN CHECK (admitted IN (true, false)),
            admission_cost INT, medicine_cost INT, doctor_fee INT,
            CONSTRAINT chk_admission_cost CHECK (
                (admitted = true AND admission_cost IS NOT NULL) OR (admitted = false AND admission_cost = 0)
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


# ════════════════════════════════════════════════════════════════
#  DELETE ROUTES  ──  with FK dependency checks
# ════════════════════════════════════════════════════════════════

@app.route("/delete/user/<int:record_id>", methods=["POST"])
def delete_user(record_id):
    try:
        # Check FK dependencies: doctor, patients
        doctors = DB().select(f"SELECT username FROM doctor WHERE username = (SELECT username FROM users WHERE id = {record_id});")
        patients = DB().select(f"SELECT username FROM patients WHERE username = (SELECT username FROM users WHERE id = {record_id});")
        user_row = DB().select(f"SELECT username FROM users WHERE id = {record_id};")
        username = user_row[0][0] if user_row else f"ID {record_id}"

        deps = []
        if doctors:
            deps.append(f"doctor (username: {', '.join(str(d[0]) for d in doctors)})")
        if patients:
            deps.append(f"patients (username: {', '.join(str(p[0]) for p in patients)})")

        if deps:
            return render_template("error9.jinja2.html",
                record_label=f"User '{username}'",
                record_id=record_id,
                parent_table="users",
                dependencies=deps,
                fix_urls=[("/doctordisplay", "Doctor Records"), ("/patientdisplay", "Patient Records")],
                back_url="/userdisplay"
            )

        DB().insert(f"DELETE FROM users WHERE id = {record_id};")
        return redirect("/userdisplay")
    except Exception as e:
        return render_template("error9.jinja2.html",
            record_label=f"User ID {record_id}",
            record_id=record_id,
            parent_table="users",
            dependencies=[str(e)],
            fix_urls=[],
            back_url="/userdisplay"
        )


@app.route("/delete/doctor/<int:record_id>", methods=["POST"])
def delete_doctor(record_id):
    try:
        doc_row = DB().select(f"SELECT username FROM doctor WHERE id = {record_id};")
        username = doc_row[0][0] if doc_row else f"ID {record_id}"

        hist = DB().select(f"SELECT COUNT(*) FROM patienthistory WHERE doctor_name = '{username}';")
        rx   = DB().select(f"SELECT COUNT(*) FROM prescription WHERE doctor_name = '{username}';")

        deps = []
        if hist and int(hist[0][0]) > 0:
            deps.append(f"patienthistory ({hist[0][0]} records)")
        if rx and int(rx[0][0]) > 0:
            deps.append(f"prescription ({rx[0][0]} records)")

        if deps:
            return render_template("error9.jinja2.html",
                record_label=f"Doctor '{username}'",
                record_id=record_id,
                parent_table="doctor",
                dependencies=deps,
                fix_urls=[("/patienthistorydisplay", "Patient History"), ("/prescriptiondisplay", "Prescriptions")],
                back_url="/doctordisplay"
            )

        DB().insert(f"DELETE FROM doctor WHERE id = {record_id};")
        return redirect("/doctordisplay")
    except Exception as e:
        return render_template("error9.jinja2.html",
            record_label=f"Doctor ID {record_id}",
            record_id=record_id,
            parent_table="doctor",
            dependencies=[str(e)],
            fix_urls=[],
            back_url="/doctordisplay"
        )


@app.route("/delete/patient/<int:record_id>", methods=["POST"])
def delete_patient(record_id):
    try:
        pat_row = DB().select(f"SELECT username FROM patients WHERE id = {record_id};")
        username = pat_row[0][0] if pat_row else f"ID {record_id}"

        hist  = DB().select(f"SELECT COUNT(*) FROM patienthistory WHERE patient_name = '{username}';")
        rx    = DB().select(f"SELECT COUNT(*) FROM prescription WHERE patient_name = '{username}';")
        costs = DB().select(f"SELECT COUNT(*) FROM costs WHERE patient_name = '{username}';")

        deps = []
        if hist  and int(hist[0][0])  > 0: deps.append(f"patienthistory ({hist[0][0]} records)")
        if rx    and int(rx[0][0])    > 0: deps.append(f"prescription ({rx[0][0]} records)")
        if costs and int(costs[0][0]) > 0: deps.append(f"costs ({costs[0][0]} records)")

        if deps:
            return render_template("error9.jinja2.html",
                record_label=f"Patient '{username}'",
                record_id=record_id,
                parent_table="patients",
                dependencies=deps,
                fix_urls=[("/patienthistorydisplay","Patient History"),("/prescriptiondisplay","Prescriptions"),("/costsdisplay","Costs")],
                back_url="/patientdisplay"
            )

        DB().insert(f"DELETE FROM patients WHERE id = {record_id};")
        return redirect("/patientdisplay")
    except Exception as e:
        return render_template("error9.jinja2.html",
            record_label=f"Patient ID {record_id}",
            record_id=record_id,
            parent_table="patients",
            dependencies=[str(e)],
            fix_urls=[],
            back_url="/patientdisplay"
        )


@app.route("/delete/patienthistory/<int:record_id>", methods=["POST"])
def delete_patienthistory(record_id):
    try:
        DB().insert(f"DELETE FROM patienthistory WHERE id = {record_id};")
        return redirect("/patienthistorydisplay")
    except Exception as e:
        return render_template("error9.jinja2.html",
            record_label=f"History Record ID {record_id}",
            record_id=record_id,
            parent_table="patienthistory",
            dependencies=[str(e)],
            fix_urls=[],
            back_url="/patienthistorydisplay"
        )


@app.route("/delete/prescription/<int:record_id>", methods=["POST"])
def delete_prescription(record_id):
    try:
        rx_row = DB().select(f"SELECT prescription_number FROM prescription WHERE id = {record_id};")
        rx_num = rx_row[0][0] if rx_row else f"ID {record_id}"

        meds = DB().select(f"SELECT COUNT(*) FROM medication WHERE prescription_number = '{rx_num}';")
        deps = []
        if meds and int(meds[0][0]) > 0:
            deps.append(f"medication ({meds[0][0]} records)")

        if deps:
            return render_template("error9.jinja2.html",
                record_label=f"Prescription '{rx_num}'",
                record_id=record_id,
                parent_table="prescription",
                dependencies=deps,
                fix_urls=[("/medicationdisplay", "Medication Records")],
                back_url="/prescriptiondisplay"
            )

        DB().insert(f"DELETE FROM prescription WHERE id = {record_id};")
        return redirect("/prescriptiondisplay")
    except Exception as e:
        return render_template("error9.jinja2.html",
            record_label=f"Prescription ID {record_id}",
            record_id=record_id,
            parent_table="prescription",
            dependencies=[str(e)],
            fix_urls=[],
            back_url="/prescriptiondisplay"
        )


@app.route("/delete/medication/<int:record_id>", methods=["POST"])
def delete_medication(record_id):
    try:
        DB().insert(f"DELETE FROM medication WHERE id = {record_id};")
        return redirect("/medicationdisplay")
    except Exception as e:
        return render_template("error9.jinja2.html",
            record_label=f"Medication ID {record_id}",
            record_id=record_id,
            parent_table="medication",
            dependencies=[str(e)],
            fix_urls=[],
            back_url="/medicationdisplay"
        )


@app.route("/delete/costs/<int:record_id>", methods=["POST"])
def delete_costs(record_id):
    try:
        DB().insert(f"DELETE FROM costs WHERE id = {record_id};")
        return redirect("/costsdisplay")
    except Exception as e:
        return render_template("error9.jinja2.html",
            record_label=f"Cost Record ID {record_id}",
            record_id=record_id,
            parent_table="costs",
            dependencies=[str(e)],
            fix_urls=[],
            back_url="/costsdisplay"
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)