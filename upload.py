import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# تهيئة الاتصال بـ Firebase بمشروع turki-2030
if not firebase_admin._apps:
  cred = credentials.Certificate("serviceAccountKey.json")
  firebase_admin.initialize_app(cred, {"projectId": "turki-2030"})

db = firestore.client()

excel_file = "المحاسب.xlsx"  # تأكد من تطابق اسم ملف الإكسل تماماً
xls = pd.ExcelFile(excel_file)

total_uploaded = 0
print("🚀 جاري بدء رفع البيانات من ملف الإكسل إلى Firebase...")

for sheet_name in xls.sheet_names:
  if sheet_name == "Mirror-2026":
    continue

  print(f"📁 معالجة الورقة: {sheet_name}...")
  df = pd.read_excel(excel_file, sheet_name=sheet_name)
  df.columns = df.columns.str.strip()

  col_mapping = {}
  for col in df.columns:
    if "تاريخ" in col:
      col_mapping[col] = "التاريخ"
    elif "مبلغ" in col:
      col_mapping[col] = "المبلغ"
    elif "نوع" in col:
      col_mapping[col] = "النوع"
    elif "بيان" in col:
      col_mapping[col] = "البيان"
    elif "اليوم" in col:
      col_mapping[col] = "اليوم"

  df = df.rename(columns=col_mapping)

  if not all(col in df.columns for col in ["التاريخ", "المبلغ", "النوع"]):
    continue

  for index, row in df.iterrows():
    date_raw = row["التاريخ"]
    if pd.isna(date_raw):
      continue

    try:
      date_str = str(pd.to_datetime(date_raw)).split(" ")[0]
      year_val = int(date_str.split("-")[0])
      month_val = int(date_str.split("-")[1])
    except:
      continue

    try:
      amount_val = float(row["المبلغ"])
      if pd.isna(amount_val):
        amount_val = 0.0
    except:
      amount_val = 0.0

    desc_val = (
        str(row["البيان"])
        if ("البيان" in df.columns and not pd.isna(row["البيان"]))
        else ""
    )
    type_val = (
        str(row["النوع"]).strip() if not pd.isna(row["النوع"]) else "إيراد"
    )

    transaction_data = {
        "date": date_str,
        "type": type_val,
        "amount": amount_val,
        "description": desc_val,
        "year": year_val,
        "month": month_val,
        "sheet_source": sheet_name,
    }

    db.collection("transactions").add(transaction_data)
    total_uploaded += 1

print(
    f"\n✅ تم بنجاح رفع جميع البيانات ({total_uploaded} حركة) إلى مشروع"
    " turki-2030!"
)