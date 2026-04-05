# TheraTrak Pro User Guide

This guide covers the main workflow for TheraTrak Pro.

## 1. Getting Started

1. Launch TheraTrak Pro.
2. Sign in with your username and password.
3. If this is first use, create an account from the login screen.

## 2. Main Tabs

- Patients: Manage demographics, insurance, referrals, and status.
- Session Notes: Document sessions, CPT codes, notes, and DSM/ICD diagnoses.
- Billing: Track charges, payments, adjustments, and balances.
- CMS-1500: Populate and export claim forms to PDF.
- Reports: View summaries and export data.
- Settings / Import: Configure provider profile and import legacy data.

## 3. User Accounts

### Create an account

1. On the login window, select Create Account.
2. Fill required fields marked with *.
3. Select role and save.

### Edit existing users

1. Open File > User Directory.
2. Select a user on the left.
3. Update fields in Edit User and select Save Changes.

### Roles

- Admin: Full access.
- User: General clinical access.
- Billing: Billing-focused workflows.
- Read-Only: View access only.

## 4. Provider Profile

1. Open File > Provider Profile (or Navigate > Provider Profile).
2. Complete Provider / Practice fields.
3. Enter NPI, Tax ID, Tax ID Type, ID Qualifier, and Taxonomy Codes.
4. Select Save Provider Settings.

Notes:
- ID Qualifier and Taxonomy Codes are used to populate CMS-1500 provider ID fields.

## 5. Patients Workflow

1. Go to Patients tab.
2. Add a patient with demographics and insurance details.
3. Save the patient record.

Tips:
- Keep insurance fields complete for cleaner CMS-1500 output.

## 6. Session Notes Workflow

1. Open Session Notes tab.
2. Create a note tied to a patient/date.
3. Enter CPT code, service details, and diagnosis.
4. Save the note.

Tips:
- Use DSM lookup for diagnosis code assistance.

## 7. Billing Workflow

1. Open Billing tab.
2. Add charge records by patient/date.
3. Post payments and adjustments.
4. Review outstanding balances.

## 8. CMS-1500 Claims

1. Open CMS-1500 tab.
2. Select Auto-Populate from Patient.
3. Choose patient and sessions.
4. Review all fields and alignment.
5. Save claim draft and/or Export PDF.

Tips:
- If claim printing alignment is off, use alignment controls and save/export offsets.

## 9. Backups and Updates

### Backup database

1. Open File > Backup Database.
2. Choose destination and save backup file.

### Check updates

1. Open Help > Check for Updates.
2. If an update is available, follow installer prompts.

## 10. Logout and Exit

- Logout: File > Logout (returns to login screen).
- Exit: File > Exit.

## 11. Troubleshooting

- App won’t open or crashes:
  - Review startup log at startup.log in the app folder.
- PDF export fails:
  - Ensure write permission to selected output folder.
- Missing data in CMS form:
  - Verify patient insurance and provider profile fields.
- Login fails:
  - Confirm username/password and active user status.

## 12. Best Practices

- Back up database daily.
- Keep provider profile accurate before billing.
- Review claims before export/submission.
- Use consistent CPT/diagnosis entry for reporting quality.
