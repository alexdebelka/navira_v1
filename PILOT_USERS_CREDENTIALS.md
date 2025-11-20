# Navira Pilot Users - Login Credentials

This document contains the login credentials for all pilot users who have limited access to specific hospitals in the Navira system.

## Overview

Pilot users are configured with the same access level as the original `andrea.lazzati` user. They have access to:
- Hospital Dashboard (automatically redirected to their assigned hospital)
- National Overview
- Hospital Explorer
- Limited Geography features

Each pilot user is automatically assigned and restricted to their specific hospital based on FINESS code.

---

## Pilot User Credentials

### 1. FEDERICA PAPINI
- **Name:** FEDERICA PAPINI
- **Center:** CHIC DE CRETEIL
- **FINESS Code:** 940000573
- **Username:** `federica.papini`
- **Password:** `12345!`
- **Email:** federica.papini@navira.com
- **Status:** Active ✅

---

### 2. LAURENT GENSER (Replaces Adriana Torcivia)
- **Name:** LAURENT GENSER
- **Center:** GROUPEMENT HOSPITALIER PITIE-SALPETRIERE
- **FINESS Code:** 750100125
- **Username:** `laurent.genser`
- **Password:** `12345!`
- **Email:** laurent.genser@navira.com
- **Status:** Active ✅

---

### 3. SERGIO CARANDINA
- **Name:** SERGIO CARANDINA
- **Center:** CLINIQUE SAINT MICHEL
- **FINESS Code:** 830100459
- **Username:** `sergio.carandina`
- **Password:** `12345!`
- **Email:** sergio.carandina@navira.com
- **Status:** Active ✅

---

### 4. CLAIRE BLANCHARD
- **Name:** CLAIRE BLANCHARD
- **Center:** CHU DE NANTES (City of Nantes)
- **FINESS Code:** 440000271
- **Username:** `claire.blanchard`
- **Password:** `12345!`
- **Email:** claire.blanchard@navira.com
- **Status:** Active ✅

---

### 5. THOMAS AUGUSTE
- **Name:** THOMAS AUGUSTE
- **Center:** CHBA VANNES (City of Vannes)
- **FINESS Code:** 560008799
- **Username:** `thomas.auguste`
- **Password:** `12345!`
- **Email:** thomas.auguste@navira.com
- **Status:** Active ✅

---

### 4. ANDREA LAZZATI (Original Pilot User)
- **Name:** ANDREA LAZZATI
- **Center:** HÔPITAL AVICENNE
- **FINESS Code:** 930100037
- **Username:** `andrea.lazzati`
- **Password:** `12345!`
- **Email:** andrea.lazzati@navira.com
- **Status:** Active ✅

---

## Technical Details

### Database Configuration
All pilot users are stored in the `users.db` database with the following configuration:
- **Role:** user
- **Is Active:** true
- **Permissions:** dashboard, national, hospital_explorer, hospital

### Authentication Flow
1. User logs in with username and password
2. System checks if username is in the pilot users list
3. If pilot user, the system:
   - Sets `_limited_user` flag to `true`
   - Automatically assigns their hospital via `selected_hospital_id`
   - Redirects to hospital dashboard for their assigned hospital
   - Enables geography features for their hospital

### File Updates
The following files have been updated to support the new pilot users:
- **`auth.py`**: Updated login logic with pilot user hospital mapping
- **`auth_wrapper.py`**: Updated authentication wrapper with pilot user hospital mapping
- **`pages/dashboard.py`**: Updated geography access to include all pilot users

### Pilot User Hospital Mapping (Code Reference)
```python
pilot_user_hospitals = {
    'andrea.lazzati': '930100037',      # Hôpital Avicenne
    'federica.papini': '940000573',     # CHIC DE CRETEIL
    'adriana.torcivia': '750100125',    # GROUPEMENT HOSPITALIER PITIE-SALPETRIERE
    'sergio.carandina': '830100459'     # CLINIQUE SAINT MICHEL
}
```

---

## Security Notes

⚠️ **Important:** 
- All pilot users currently use the same temporary password (`12345!`)
- Users should be encouraged to change their password after first login (feature to be implemented)
- Passwords are hashed using SHA-256 before storage
- Session tokens expire after 24 hours

---

## Access Restrictions

Pilot users have the following restrictions:
- Can only view data for their assigned hospital
- Cannot access the admin panel
- Cannot switch hospitals (locked to their FINESS code)
- Automatically redirected to their hospital dashboard upon login

---

## Adding New Pilot Users

To add additional pilot users in the future:

1. **Create the user in the database:**
   ```python
   from auth import create_user
   create_user(username, email, password, role='user')
   ```

2. **Update the pilot user mapping in three files:**
   - `auth.py` (line ~446)
   - `auth_wrapper.py` (line ~41)
   - `pages/dashboard.py` (line ~647)

3. **Add the mapping:**
   ```python
   'username': 'FINESS_CODE',  # Hospital Name
   ```

---

## Date Created
**November 8, 2025**

## Created By
System Administrator

---

*This document should be kept secure and only shared with authorized personnel.*

