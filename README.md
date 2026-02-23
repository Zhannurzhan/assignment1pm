# Clinic Management System

A FastAPI-based backend system for managing clinical appointments with role-based access control, spatial analytics using H3, and an event-driven architecture.

---

## How to Run the System

### Prerequisites

- Python 3.11+
- pip

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd clinic_management
```

### 2. Create and Activate Virtual Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory:

```env
SECRET_KEY=your-secret-key-minimum-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 5. Run the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at: **http://127.0.0.1:8000**  
Interactive docs (Swagger UI): **http://127.0.0.1:8000/docs**

---

## 📋 API Usage Flow

Follow these steps in order to use the system:

**Step 1 — Register a user**
```
POST /register
{
  "username": "john",
  "email": "john@example.com",
  "password": "password123",
  "role": "Patient"   ← Patient | Doctor | Admin
}
```

**Step 2 — Login to get a token**
```
POST /login
username: john@example.com
password: password123
```
Copy the `access_token` from the response and use it in the Swagger **Authorize** button.

**Step 3 — Set up patient profile (Patient role only)**
```
POST /setup-patient?latitude=40.7128&longitude=-74.0060
```

**Step 4 — Create an appointment (Patient role only)**
```
POST /appointments
{
  "doctor_id": 1,
  "datetime": "2025-06-01T10:00:00"
}
```

**Step 5 — View your appointments**
```
GET /appointments/my
```

**Step 6 — View regional analytics (Admin role only)**
```
GET /analytics/{h3_index}
```

**Step 7 — View audit logs (Admin role only)**
```
GET /audit-logs
```

---

## 👥 Group Member Roles

| Member                 | Role               |
| ---------------------- | ------------------ |
| **Seiitkhan Zhannur**  | Backend Developer  |
| **Ruslan Ussen**       | Frontend Developer |
| **Askhat Yeleubay**    | Frontend Developer |
| **Margulan Baizhigit** | Mobile Developer   |


## How H3 is Used in the System

[H3](https://h3geo.org/) is Uber's open-source hexagonal hierarchical geospatial indexing system. This project uses H3 to add a **spatial dimension** to clinical appointments.

### How It Works

**1. Patient Registration with Location**

When a patient sets up their profile via `POST /setup-patient`, their latitude and longitude are converted into an **H3 cell index** at resolution 7 (~5.16 km² hexagons):

```python
import h3
h3_index = h3.latlng_to_cell(latitude, longitude, resolution=7)
# e.g. "872b8e254ffffff"
```

This H3 index is stored on the `Patient` record in the database.

**2. Appointments Inherit Spatial Context**

When an appointment is created, it automatically inherits the patient's H3 index:

```python
new_appt = Appointment(
    patient_id=patient.id,
    doctor_id=doctor_id,
    h3_index=patient.h3_index,  # ← spatial tag copied from patient
    ...
)
```

This means every appointment is geographically tagged to the region the patient is located in.

**3. Regional Analytics**

Admins can query appointment statistics grouped by H3 region:

```
GET /analytics/{h3_index}
```

This returns all appointments that occurred within that hexagonal region, enabling insights such as:
- Which regions have the highest appointment volume
- Identifying underserved geographic areas
- Optimising doctor allocation by region

### Why H3?

| Feature | Benefit |
|---------|---------|
| Hexagonal grid | Uniform neighbor distances (unlike square grids) |
| Hierarchical | Can zoom in/out between resolutions (0–15) |
| Compact index | A region stored as a single string e.g. `"872b8e254ffffff"` |
| Fast grouping | Aggregate thousands of records by region with simple string matching |

---

##  Project Structure

```
clinic_management/
├── app/
│   ├── main.py              # FastAPI app, routes
│   ├── auth.py              # JWT auth, password hashing, RoleChecker
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── database.py          # Async database engine and session
│   ├── config.py            # App settings (.env)
│   └── services/
│       ├── appointment.py   # Appointment creation logic
│       ├── audit_service.py # Audit logging
│       ├── event_service.py # Event-driven handlers
│       └── h3_service.py    # H3 spatial aggregation
├── blog.db                  # SQLite database (auto-created)
├── requirements.txt
└── README.md
```

---

## Roles & Permissions

| Endpoint | Patient | Doctor | Admin |
|----------|---------|--------|-------|
| `POST /register` | ✅ | ✅ | ✅ |
| `POST /login` | ✅ | ✅ | ✅ |
| `POST /setup-patient` | ✅ | ❌ | ❌ |
| `POST /appointments` | ✅ | ❌ | ❌ |
| `GET /appointments/my` | ✅ | ✅ | ❌ |
| `GET /analytics/{h3}` | ❌ | ❌ | ✅ |
| `GET /audit-logs` | ❌ | ❌ | ✅ |

---

## ⚠️ Known Issues & Notes

- The JWT secret key should be **at least 32 characters** to avoid `InsecureKeyLengthWarning`
- A `Doctor` user must also have a record in the `doctors` table to be bookable as an appointment target
- The SQLite database file (`blog.db`) is auto-created on first startup