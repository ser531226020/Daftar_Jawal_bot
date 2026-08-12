import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# تهيئة الاتصال بـ Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def import_financial_excel(file_name):
    print("جاري قراءة جميع الشيتات وتصفية البيانات وترتيبها...")
    
    # قراءة كل الشيتات الموجودة في ملف الإكسل كقاموس (Sheet Name -> DataFrame)
    all_sheets = pd.read_excel(file_name, sheet_name=None)
    
    combined_df_list = []
    
    # المرور على كل شيت على حدة وتجهيز بياناته
    for sheet_name, df in all_sheets.items():
        if df.empty:
            continue
            
        # إزالة المسافات الزائدة من أسماء الأعمدة إن وجدت
        df.columns = df.columns.str.strip()
        
        # التأكد من أن الشيت يحتوي على الأعمدة الأربعة الأساسية حسب ترتيب صورتك
        # العمود A: التاريخ، العمود B: البيان، العمود C: المبلغ، العمود D: النوع
        if len(df.columns) >= 4:
            temp_df = pd.DataFrame()
            temp_df['التاريخ'] = df.iloc[:, 0]
            temp_df['البيان'] = df.iloc[:, 1]
            temp_df['المبلغ'] = df.iloc[:, 2]
            temp_df['النوع'] = df.iloc[:, 3]
            
            combined_df_list.append(temp_df)
            
    if not combined_df_list:
        print("لم يتم العثور على بيانات صالحه للرفع في الشيتات!")
        return
        
    # دمج بيانات كل الشيتات في جدول واحد كبير
    full_df = pd.concat(combined_df_list, ignore_index=True)
    
    # تنظيف وترتيب البيانات حسب التاريخ تصاعدياً
    full_df['التاريخ'] = pd.to_datetime(full_df['التاريخ'], errors='coerce')
    full_df = full_df.dropna(subset=['التاريخ']) # حذف الصفوف التي لا تحتوي على تاريخ صحيح
    full_df['التاريخ_str'] = full_df['التاريخ'].dt.strftime('%Y-%m-%d')
    full_df = full_df.sort_values(by='التاريخ')
    
    batch = db.batch()
    count = 0
    total_imported = 0
    
    for index, row in full_df.iterrows():
        date_str = row['التاريخ_str']
        date_obj = row['التاريخ']
        
        year_val = int(date_obj.year)
        month_val = int(date_obj.month)
        
        # تنظيف المبلغ وتحويله برقم دقيق
        try:
            amount_val = float(row['المبلغ'])
        except (ValueError, TypeError):
            amount_val = 0.0
            
        doc_ref = db.collection('transactions').document()
        payload = {
            "date": date_str,
            "description": str(row['البيان']) if pd.notna(row['البيان']) else "",
            "amount": amount_val,
            "type": str(row['النوع']) if pd.notna(row['النوع']) else "إيراد",
            "year": year_val,
            "month": month_val
        }
        
        batch.set(doc_ref, payload)
        count += 1
        total_imported += 1
        
        if count >= 400:
            batch.commit()
            batch = db.batch()
            count = 0
            
    batch.commit()
    print(f"تم بنجاح رفع وترتيب عدد {total_imported} حركة مالية من جميع الشيتات إلى قاعدة البيانات!")

if __name__ == "__main__":
    import_financial_excel("data.xlsx")