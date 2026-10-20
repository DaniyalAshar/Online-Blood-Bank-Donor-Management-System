import os, csv, io
from datetime import datetime, date, timedelta
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///lifeflow.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "60 per hour"])

GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
URGENCIES = ["routine", "urgent", "critical"]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(25))
    role = db.Column(db.String(20), nullable=False, default="donor")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Donor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    blood_type = db.Column(db.String(3), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    available = db.Column(db.Boolean, default=False, nullable=False)
    contact_consent = db.Column(db.Boolean, default=False, nullable=False)
    last_donation_date = db.Column(db.Date)
    eligibility_status = db.Column(db.String(24), default="review_required", nullable=False)
    user = db.relationship("User", backref="donor_profile")

class Facility(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    facility_type = db.Column(db.String(20), default="blood_bank", nullable=False)
    verified = db.Column(db.Boolean, default=False, nullable=False)
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(25))

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"), nullable=False)
    blood_type = db.Column(db.String(3), nullable=False)
    component_type = db.Column(db.String(30), default="red_cells", nullable=False)
    units_available = db.Column(db.Integer, default=0, nullable=False)
    units_reserved = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    facility = db.relationship("Facility", backref="inventory")
    __table_args__ = (db.UniqueConstraint("facility_id", "blood_type", "component_type"),)

class BloodRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_name = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(100), nullable=False)
    blood_type = db.Column(db.String(3), nullable=False)
    units_needed = db.Column(db.Integer, nullable=False)
    hospital = db.Column(db.String(180), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    urgency = db.Column(db.String(20), default="urgent", nullable=False)
    status = db.Column(db.String(20), default="pending_review", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey("donor.id"), nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"))
    donation_date = db.Column(db.Date, nullable=False)
    units = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(20), default="completed", nullable=False)
    donor = db.relationship("Donor", backref="donations")
    facility = db.relationship("Facility", backref="donations")

@app.context_processor
def inject_globals():
    return {"blood_groups": GROUPS}

@app.get("/")
def home(): return render_template("home.html")

@app.get("/search")
def search_page(): return render_template("search.html")

@app.route("/donor/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def donor_register():
    if request.method == "POST":
        name=request.form.get("full_name","").strip()
        email=request.form.get("email","").strip().lower()
        phone=request.form.get("phone","").strip()
        group=request.form.get("blood_type","")
        city=request.form.get("city","").strip()
        consent=request.form.get("contact_consent")=="on"
        if len(name)<2 or "@" not in email or not phone or group not in GROUPS or not city:
            flash("Please complete all required fields correctly.","error"); return redirect(url_for("donor_register"))
        if User.query.filter_by(email=email).first():
            flash("That email is already registered in this demo.","error"); return redirect(url_for("donor_register"))
        user=User(full_name=name,email=email,phone=phone,role="donor")
        db.session.add(user); db.session.flush()
        db.session.add(Donor(user_id=user.id,blood_type=group,city=city,contact_consent=consent,available=False,eligibility_status="review_required"))
        db.session.commit()
        flash("Registration saved. A donation center must review eligibility before matching.","success")
        return redirect(url_for("dashboard"))
    return render_template("donor_register.html")

@app.route("/request/new", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def new_request():
    if request.method=="POST":
        name=request.form.get("requester_name","").strip(); contact=request.form.get("contact","").strip()
        group=request.form.get("blood_type",""); hospital=request.form.get("hospital","").strip(); city=request.form.get("city","").strip()
        try: units=int(request.form.get("units_needed","0"))
        except ValueError: units=0
        urgency=request.form.get("urgency","urgent")
        if not name or not contact or group not in GROUPS or not hospital or not city or not (1<=units<=100) or urgency not in URGENCIES:
            flash("Please check the request details and try again.","error"); return redirect(url_for("new_request"))
        db.session.add(BloodRequest(requester_name=name,contact=contact,blood_type=group,units_needed=units,hospital=hospital,city=city,urgency=urgency))
        db.session.commit(); flash("Request submitted for review. This demo does not send emergency alerts.","success")
        return redirect(url_for("dashboard"))
    return render_template("request.html")

@app.get("/dashboard")
def dashboard():
    counts=metrics()
    recent=BloodRequest.query.order_by(BloodRequest.created_at.desc()).limit(5).all()
    return render_template("dashboard.html",counts=counts,recent_requests=recent)

@app.get("/analytics")
def analytics_page(): return render_template("analytics.html")

@app.get("/about")
def about(): return render_template("about.html")

@app.get("/api/health")
def health(): return jsonify(status="ok")

@app.get("/api/inventory/search")
@limiter.limit("30 per minute")
def search_inventory():
    group=request.args.get("bloodType",""); city=request.args.get("city","").strip()
    if group not in GROUPS: return jsonify(error="Choose a valid blood group"),400
    q=db.session.query(Inventory,Facility).join(Facility).filter(Inventory.blood_type==group,Facility.verified.is_(True))
    if city: q=q.filter(Facility.city.ilike(f"%{city}%"))
    items=[]
    for inv,fac in q.order_by(Facility.city,Facility.name).limit(100).all():
        units=max(0,inv.units_available-inv.units_reserved)
        if units: items.append({"facilityName":fac.name,"address":fac.address,"city":fac.city,"phone":fac.phone or "Contact facility","availableUnits":units,"updatedAt":inv.updated_at.isoformat()})
    return jsonify(items=items)

def metrics():
    donors=Donor.query.count()
    facilities=Facility.query.filter_by(verified=True).count()
    requests=BloodRequest.query.count()
    units=db.session.query(db.func.sum(Inventory.units_available-Inventory.units_reserved)).join(Facility).filter(Facility.verified.is_(True)).scalar() or 0
    fulfilled=BloodRequest.query.filter_by(status="fulfilled").count()
    fill_rate=round(100*fulfilled/requests,1) if requests else 0
    return {"donors":donors,"facilities":facilities,"requests":requests,"units":max(0,units),"fill_rate":fill_rate}

def analytics_payload(city="", group=""):
    invq=db.session.query(Inventory,Facility).join(Facility).filter(Facility.verified.is_(True))
    reqq=BloodRequest.query
    donq=Donor.query
    if city:
        invq=invq.filter(Facility.city.ilike(f"%{city}%"))
        reqq=reqq.filter(BloodRequest.city.ilike(f"%{city}%"))
        donq=donq.filter(Donor.city.ilike(f"%{city}%"))
    if group:
        invq=invq.filter(Inventory.blood_type==group)
        reqq=reqq.filter(BloodRequest.blood_type==group)
        donq=donq.filter(Donor.blood_type==group)
    stock={g:0 for g in GROUPS}; facilities={}
    for inv,fac in invq.all():
        stock[inv.blood_type]=stock.get(inv.blood_type,0)+max(0,inv.units_available-inv.units_reserved)
        facilities[fac.name]=facilities.get(fac.name,0)+max(0,inv.units_available-inv.units_reserved)
    request_rows=reqq.order_by(BloodRequest.created_at.asc()).all()
    monthly={}
    for r in request_rows:
        key=r.created_at.strftime("%Y-%m")
        monthly[key]=monthly.get(key,0)+1
    # Show a continuous 6-month axis so empty months remain visible.
    now=date.today().replace(day=1)
    months=[]
    for back in range(5,-1,-1):
        y=now.year; m=now.month-back
        while m<=0: y-=1; m+=12
        key=f"{y:04d}-{m:02d}"; months.append({"month":key,"requests":monthly.get(key,0)})
    urgency={u:0 for u in URGENCIES}
    for r in request_rows: urgency[r.urgency]=urgency.get(r.urgency,0)+1
    donor_count=donq.count()
    total_units=sum(stock.values())
    requests_count=len(request_rows)
    fulfilled=sum(1 for r in request_rows if r.status=="fulfilled")
    return {"filters":{"city":city,"bloodType":group},"kpis":{"donors":donor_count,"requests":requests_count,"availableUnits":total_units,"facilities":len(facilities),"fillRateProxy":round(fulfilled*100/requests_count,1) if requests_count else 0},
            "stockByGroup":[{"group":g,"units":stock.get(g,0)} for g in GROUPS],
            "requestsByMonth":months,
            "urgencyMix":[{"urgency":u,"count":urgency[u]} for u in URGENCIES],
            "stockByFacility":[{"facility":k,"units":v} for k,v in sorted(facilities.items(),key=lambda x:x[1],reverse=True)[:8]],
            "insights":{"highestStockGroup":max(stock,key=stock.get) if total_units else "No data","mostCommonUrgency":max(urgency,key=urgency.get) if requests_count else "No data","averageUnitsPerFacility":round(total_units/len(facilities),1) if facilities else 0}}

@app.get("/api/analytics")
@limiter.limit("30 per minute")
def analytics_api():
    city=request.args.get("city","").strip()[:100]
    group=request.args.get("bloodType","").strip()
    if group and group not in GROUPS: return jsonify(error="Invalid blood group"),400
    return jsonify(analytics_payload(city,group))

@app.get("/api/analytics/export.csv")
@limiter.limit("10 per hour")
def export_analytics():
    # Pandas provides a consistent export format for the aggregated analytics payload.
    import pandas as pd
    payload=analytics_payload(request.args.get("city","").strip()[:100],request.args.get("bloodType","").strip())
    df=pd.DataFrame(payload["stockByGroup"])
    output=io.StringIO(); df.to_csv(output,index=False)
    return Response(output.getvalue(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=lifeflow-stock-by-group.csv"})

@app.get("/api/demo/seed")
@limiter.limit("3 per hour")
def demo_seed():
    if os.getenv("FLASK_DEBUG","0").lower() not in ("1","true"): return jsonify(error="Not found"),404
    if Facility.query.first(): return jsonify(message="Demo data already exists")
    today=date.today()
    samples=[
      ("LifeFlow City Blood Center","Central Road","Solapur","A+",12),("LifeFlow City Blood Center","Central Road","Solapur","O+",18),
      ("LifeFlow City Blood Center","Central Road","Solapur","B+",7),("LifeFlow City Blood Center","Central Road","Solapur","AB+",4),
      ("Hope Hospital Blood Unit","Market Street","Solapur","O-",3),("Hope Hospital Blood Unit","Market Street","Solapur","A-",5),
      ("Community Blood Bank","Station Road","Pune","B-",2),("Community Blood Bank","Station Road","Pune","AB-",4),
      ("Community Blood Bank","Station Road","Pune","O+",9),("Hope Hospital Blood Unit","Market Street","Solapur","B+",6)]
    facs={}
    for name,address,city,group,units in samples:
        if name not in facs:
            fac=Facility(name=name,address=address,city=city,verified=True,phone="Demo contact")
            db.session.add(fac); db.session.flush(); facs[name]=fac
        db.session.add(Inventory(facility_id=facs[name].id,blood_type=group,units_available=units,units_reserved=0,updated_at=datetime.utcnow()-timedelta(hours=(len(facs)*3))))
    # synthetic donors
    donor_specs=[("Asha Demo","asha.demo@example.test","A+","Solapur"),("Rahul Demo","rahul.demo@example.test","O+","Solapur"),("Noor Demo","noor.demo@example.test","B+","Pune"),("Mira Demo","mira.demo@example.test","O-","Solapur"),("Dev Demo","dev.demo@example.test","AB+","Pune")]
    donors=[]
    for name,email,group,city in donor_specs:
        user=User(full_name=name,email=email,phone="0000000000",role="donor"); db.session.add(user); db.session.flush()
        d=Donor(user_id=user.id,blood_type=group,city=city,available=True,contact_consent=False,eligibility_status="review_required")
        db.session.add(d); db.session.flush(); donors.append(d)
    for i,(group,urgency,city,status) in enumerate([("O+","critical","Solapur","pending_review"),("A+","urgent","Solapur","pending_review"),("B+","routine","Pune","fulfilled"),("O-","critical","Solapur","pending_review"),("AB+","urgent","Pune","pending_review"),("A-","routine","Solapur","fulfilled")]):
        db.session.add(BloodRequest(requester_name=f"Demo Request {i+1}",contact="demo@example.test",blood_type=group,units_needed=(i%3)+1,hospital="Demo General Hospital",city=city,urgency=urgency,status=status,created_at=datetime.combine(today-timedelta(days=25-i*5),datetime.min.time())))
    for i,d in enumerate(donors):
        db.session.add(Donation(donor_id=d.id,facility_id=list(facs.values())[i%len(facs)].id,donation_date=today-timedelta(days=45+i*22),units=1,status="completed"))
    db.session.commit()
    return jsonify(message="Synthetic demo analytics data created",note="Use only for software demonstration.")

with app.app_context():
    db.create_all()

if __name__=="__main__":
    app.run(host="127.0.0.1",port=int(os.getenv("PORT","5000")),debug=os.getenv("FLASK_DEBUG","0").lower() in ("1","true"))
