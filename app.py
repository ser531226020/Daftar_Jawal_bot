from datetime import datetime
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, jsonify, render_template_string, request

if 'FIREBASE_CONFIG_JSON' in os.environ:
    try:
        raw_config = os.environ['FIREBASE_CONFIG_JSON'].strip()
        # تنظيف علامات التنصيص الزائدة إن وجدت
        if raw_config.startswith("'") and raw_config.endswith("'"):
            raw_config = raw_config[1:-1]
        elif raw_config.startswith('"') and raw_config.endswith('"'):
            raw_config = raw_config[1:-1]
            
        firebase_config = json.loads(raw_config)
        cred = credentials.Certificate(firebase_config)
    except Exception as e:
        raise ValueError(f"فشل قراءة متغير البيئة FIREBASE_CONFIG_JSON كـ JSON صحيح: {e}")
elif os.path.exists("serviceAccountKey.json"):
    cred = credentials.Certificate("serviceAccountKey.json")
else:
    raise FileNotFoundError("تنبيه هام: لم يتم العثور على ملف serviceAccountKey.json محلياً ولا متغير البيئة FIREBASE_CONFIG_JSON!")

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {"projectId": "turki-2030"})

db = firestore.client()
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>النظام المالي المؤسسي - V1.0</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap" rel="stylesheet">
    <style> body { font-family: 'Cairo', sans-serif; } </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen py-8 px-4">
    <div class="max-w-7xl mx-auto space-y-6">
        
        <!-- الهيدر المؤسسي -->
        <div class="bg-slate-900/90 backdrop-blur-xl shadow-2xl rounded-3xl p-6 border border-slate-800 flex flex-wrap justify-between items-center gap-4">
            <div class="flex items-center space-x-4 space-x-reverse">
                <div class="w-14 h-14 bg-gradient-to-tr from-indigo-600 to-violet-600 rounded-2xl flex items-center justify-center shadow-xl shadow-indigo-600/30 text-3xl font-black text-white">ط</div>
                <div>
                    <h1 class="text-2xl font-black tracking-wide text-white">النظام المحاسبي الذكي</h1>
                    <p class="text-xs text-indigo-400 font-bold mt-1">V1.0 | تركي المحمادي</p>
                </div>
            </div>
            <span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold px-4 py-2 rounded-xl flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span> متصل بـ Firebase
            </span>
        </div>

        <!-- أزرار التبويبات -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-900/60 p-2 rounded-3xl border border-slate-800">
            <button onclick="switchTab('input')" id="tabBtnInput" 
                class="py-4 text-sm font-black rounded-2xl transition-all duration-300 bg-indigo-600 text-white shadow-xl shadow-indigo-600/30 flex items-center justify-center gap-2 cursor-pointer">
                ➕ تسجيل حركة مالية جديدة
            </button>
            <button onclick="switchTab('reports')" id="tabBtnReports" 
                class="py-4 text-sm font-black rounded-2xl transition-all duration-300 bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-white flex items-center justify-center gap-2 cursor-pointer">
                📊 التقارير المالية المتقدمة
            </button>
        </div>

        <!-- التبويب الأول: تسجيل حركة جديدة -->
        <div id="tabInput" class="bg-slate-900/90 shadow-2xl rounded-3xl p-8 border border-slate-800 max-w-3xl mx-auto space-y-6">
            <h2 id="formTitle" class="text-xl font-black text-white pb-4 border-b border-slate-800">تسجيل حركة مالية جديدة</h2>
            <form id="txForm" class="space-y-5">
                <input type="hidden" id="editId" value="">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div>
                        <label class="block text-xs font-bold text-slate-300 mb-2">تاريخ الحركة</label>
                        <input type="date" id="date" required 
                            class="w-full px-4 py-3.5 rounded-2xl bg-slate-950 border border-slate-800 focus:ring-2 focus:ring-indigo-500 text-slate-200 outline-none">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-300 mb-2">نوع الحركة</label>
                        <select id="type" required 
                            class="w-full px-4 py-3.5 rounded-2xl bg-slate-950 border border-slate-800 focus:ring-2 focus:ring-indigo-500 text-slate-200 outline-none">
                            <option value="إيراد">إيراد 📈</option>
                            <option value="مصروف">مصروف 📉</option>
                        </select>
                    </div>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-300 mb-2">المبلغ</label>
                    <input type="number" step="0.01" id="amount" placeholder="0.00" required 
                        class="w-full px-4 py-3.5 rounded-2xl bg-slate-950 border border-slate-800 focus:ring-2 focus:ring-indigo-500 text-slate-200 outline-none font-bold text-lg text-emerald-400">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-300 mb-2">البيان / الوصف</label>
                    <textarea id="description" rows="3" placeholder="تفاصيل الحركة أو مصدر الإيراد/المصروف..." 
                        class="w-full px-4 py-3.5 rounded-2xl bg-slate-950 border border-slate-800 focus:ring-2 focus:ring-indigo-500 text-slate-200 outline-none"></textarea>
                </div>
                <div class="flex gap-3">
                    <button type="submit" id="submitBtn"
                        class="flex-1 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-black py-4 rounded-2xl transition shadow-xl shadow-indigo-600/30 text-base cursor-pointer">
                        حفظ في قاعدة البيانات
                    </button>
                    <button type="button" id="cancelEditBtn" onclick="resetForm()" class="hidden bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold px-6 py-4 rounded-2xl transition cursor-pointer">
                        إلغاء التعديل
                    </button>
                </div>
            </form>
            <div id="msg" class="hidden mt-4 p-4 rounded-2xl text-center text-sm font-bold"></div>
        </div>

        <!-- التبويب الثاني: التقارير المالية المتقدمة -->
        <div id="tabReports" class="hidden space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
                <div class="bg-gradient-to-br from-emerald-950/60 via-slate-900 to-slate-900 p-6 rounded-3xl border border-emerald-500/30 shadow-2xl relative overflow-hidden">
                    <p class="text-xs text-emerald-400 font-black uppercase tracking-wider">إجمالي الإيرادات الكلي</p>
                    <p id="totalRevenue" class="text-4xl font-black text-emerald-300 mt-2">0.00</p>
                </div>
                <div class="bg-gradient-to-br from-rose-950/60 via-slate-900 to-slate-900 p-6 rounded-3xl border border-rose-500/30 shadow-2xl relative overflow-hidden">
                    <p class="text-xs text-rose-400 font-black uppercase tracking-wider">إجمالي المصروفات الكلي</p>
                    <p id="totalExpense" class="text-4xl font-black text-rose-300 mt-2">0.00</p>
                </div>
                <div class="bg-gradient-to-br from-blue-950/60 via-slate-900 to-slate-900 p-6 rounded-3xl border border-blue-500/30 shadow-2xl relative overflow-hidden">
                    <p class="text-xs text-blue-400 font-black uppercase tracking-wider">الصافي الكلي (الربح/العجز)</p>
                    <p id="netProfit" class="text-4xl font-black text-blue-300 mt-2">0.00</p>
                </div>
            </div>

            <!-- لوحة الفرز والفلترة -->
            <div class="bg-slate-900/90 p-6 rounded-3xl border border-slate-800 shadow-xl space-y-5">
                <div class="flex flex-wrap items-center justify-between gap-4">
                    <h3 class="text-base font-black text-indigo-300">🔍 تصفية التقارير حسب السنوات والشهور</h3>
                    <div class="flex gap-3">
                        <button onclick="loadReport()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-black px-4 py-2.5 rounded-xl border border-slate-700 transition cursor-pointer">🔄 تحديث البيانات</button>
                        <button onclick="exportToCSV()" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-black px-4 py-2.5 rounded-xl transition cursor-pointer">📥 تصدير CSV</button>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <div class="space-y-4">
                        <div>
                            <label class="block text-xs font-bold text-slate-400 mb-2">اختر السنة المالية:</label>
                            <select id="yearSelect" onchange="onYearChange()" class="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-slate-800 text-slate-200 font-bold outline-none">
                                <option value="all">جميع السنوات (عرض الكل)</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-400 mb-2">اختر الشهر:</label>
                            <select id="monthSelect" onchange="renderFilteredReport()" class="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-slate-800 text-slate-200 font-bold outline-none" disabled>
                                <option value="all">جميع شهور السنة المختارة</option>
                            </select>
                        </div>
                    </div>

                    <!-- إجمالي السنة المختارة -->
                    <div class="bg-gradient-to-br from-indigo-950/50 via-slate-950 to-slate-950 p-5 rounded-2xl border border-indigo-500/30 flex flex-col justify-between shadow-inner">
                        <div class="flex justify-between items-center border-b border-indigo-500/20 pb-3">
                            <span id="selectedYearTitle" class="text-sm font-black text-indigo-300">📅 إجمالي السنة المحددة</span>
                            <span class="text-[10px] bg-indigo-500/20 text-indigo-300 px-2.5 py-1 rounded-lg font-bold">ملخص سنوي</span>
                        </div>
                        <div class="grid grid-cols-3 gap-2 pt-3 text-center">
                            <div class="bg-slate-900/80 p-2.5 rounded-xl border border-slate-800">
                                <span class="block text-[10px] text-emerald-400 font-bold">إيرادات السنة</span>
                                <span id="yearRev" class="text-sm font-black text-emerald-300">0.00</span>
                            </div>
                            <div class="bg-slate-900/80 p-2.5 rounded-xl border border-slate-800">
                                <span class="block text-[10px] text-rose-400 font-bold">مصروفات السنة</span>
                                <span id="yearExp" class="text-sm font-black text-rose-300">0.00</span>
                            </div>
                            <div class="bg-slate-900/80 p-2.5 rounded-xl border border-slate-800">
                                <span class="block text-[10px] text-blue-400 font-bold">صافي السنة</span>
                                <span id="yearNet" class="text-sm font-black text-blue-300">0.00</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- حاوية عرض النتائج المفلترة -->
            <div id="filteredReportContainer" class="space-y-6"></div>
        </div>
    </div>

    <script>
        document.getElementById('date').value = new Date().toISOString().split('T')[0];
        let globalTransactions = [];
        let globalTree = {};

        const dayNames = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'];
        const monthNames = {
            "01": "يناير", "02": "فبراير", "03": "مارس", "04": "أبريل", 
            "05": "مايو", "06": "يونيو", "07": "يوليو", "08": "أغسطس", 
            "09": "سبتمبر", "10": "أكتوبر", "11": "نوفمبر", "12": "ديسمبر"
        };

        function getDayNameArabic(dateStr) {
            const d = new Date(dateStr);
            return dayNames[d.getDay()];
        }

        function switchTab(tab) {
            const inputTab = document.getElementById('tabInput');
            const reportsTab = document.getElementById('tabReports');
            const btnInput = document.getElementById('tabBtnInput');
            const btnReports = document.getElementById('tabBtnReports');

            if(tab === 'input') {
                inputTab.classList.remove('hidden');
                reportsTab.classList.add('hidden');
                btnInput.className = "py-4 text-sm font-black rounded-2xl transition-all duration-300 bg-indigo-600 text-white shadow-xl shadow-indigo-600/30 flex items-center justify-center gap-2 cursor-pointer";
                btnReports.className = "py-4 text-sm font-black rounded-2xl transition-all duration-300 bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-white flex items-center justify-center gap-2 cursor-pointer";
            } else {
                inputTab.classList.add('hidden');
                reportsTab.classList.remove('hidden');
                btnReports.className = "py-4 text-sm font-black rounded-2xl transition-all duration-300 bg-indigo-600 text-white shadow-xl shadow-indigo-600/30 flex items-center justify-center gap-2 cursor-pointer";
                btnInput.className = "py-4 text-sm font-black rounded-2xl transition-all duration-300 bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-white flex items-center justify-center gap-2 cursor-pointer";
                loadReport();
            }
        }

        async function loadReport() {
            try {
                const res = await fetch('/api/report');
                const data = await res.json();
                
                document.getElementById('totalRevenue').innerText = data.total_revenue.toLocaleString('en-US', {minimumFractionDigits: 2});
                document.getElementById('totalExpense').innerText = data.total_expense.toLocaleString('en-US', {minimumFractionDigits: 2});
                document.getElementById('netProfit').innerText = data.net.toLocaleString('en-US', {minimumFractionDigits: 2});

                globalTransactions = data.transactions;
                buildTreeAndYears(globalTransactions);
            } catch(e) {
                console.error("خطأ في جلب البيانات", e);
            }
        }

        function buildTreeAndYears(transactions) {
            globalTree = {};
            transactions.forEach(tx => {
                const parts = tx.date.split('-');
                const year = parts[0];
                const month = parts[1];

                if(!globalTree[year]) globalTree[year] = { rev: 0, exp: 0, net: 0, months: {} };
                if(!globalTree[year].months[month]) globalTree[year].months[month] = { rev: 0, exp: 0, net: 0, txs: [] };

                globalTree[year].months[month].txs.push(tx);
                if(tx.type === 'إيراد') {
                    globalTree[year].months[month].rev += tx.amount;
                    globalTree[year].rev += tx.amount;
                } else {
                    globalTree[year].months[month].exp += tx.amount;
                    globalTree[year].exp += tx.amount;
                }
            });

            Object.keys(globalTree).forEach(year => {
                globalTree[year].net = globalTree[year].rev - globalTree[year].exp;
                Object.keys(globalTree[year].months).forEach(month => {
                    let m = globalTree[year].months[month];
                    m.net = m.rev - m.exp;
                });
            });

            const yearSelect = document.getElementById('yearSelect');
            const currentSelectedYear = yearSelect.value;
            yearSelect.innerHTML = '<option value="all">جميع السنوات (عرض الكل)</option>';
            
            const sortedYears = Object.keys(globalTree).sort().reverse();
            sortedYears.forEach(y => {
                const opt = document.createElement('option');
                opt.value = y;
                opt.innerText = `سنة ${y}`;
                yearSelect.appendChild(opt);
            });

            if(sortedYears.includes(currentSelectedYear)) {
                yearSelect.value = currentSelectedYear;
            } else if(sortedYears.length > 0 && currentSelectedYear === 'all') {
                yearSelect.value = sortedYears[0];
            }

            onYearChange(false);
        }

        function onYearChange(resetMonth = true) {
            const yearVal = document.getElementById('yearSelect').value;
            const monthSelect = document.getElementById('monthSelect');
            
            let yRev = 0, yExp = 0, yNet = 0;
            if(yearVal === 'all') {
                document.getElementById('selectedYearTitle').innerText = "📅 إجمالي كافة السنوات";
                Object.values(globalTree).forEach(y => {
                    yRev += y.rev;
                    yExp += y.exp;
                    yNet += y.net;
                });
            } else {
                document.getElementById('selectedYearTitle').innerText = `📅 إجمالي سنة ${yearVal}`;
                if(globalTree[yearVal]) {
                    yRev = globalTree[yearVal].rev;
                    yExp = globalTree[yearVal].exp;
                    yNet = globalTree[yearVal].net;
                }
            }
            document.getElementById('yearRev').innerText = yRev.toLocaleString('en-US', {minimumFractionDigits: 2});
            document.getElementById('yearExp').innerText = yExp.toLocaleString('en-US', {minimumFractionDigits: 2});
            document.getElementById('yearNet').innerText = yNet.toLocaleString('en-US', {minimumFractionDigits: 2});

            if(yearVal === 'all') {
                monthSelect.innerHTML = '<option value="all">اختر السنة أولاً...</option>';
                monthSelect.disabled = true;
            } else {
                monthSelect.disabled = false;
                monthSelect.innerHTML = '<option value="all">جميع شهور سنة ' + yearVal + '</option>';
                if(globalTree[yearVal]) {
                    const sortedMonths = Object.keys(globalTree[yearVal].months).sort().reverse();
                    sortedMonths.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m;
                        opt.innerText = monthNames[m] + ' (' + m + ')';
                        monthSelect.appendChild(opt);
                    });
                }
            }
            if(resetMonth) monthSelect.value = 'all';
            renderFilteredReport();
        }

        function renderFilteredReport() {
            const yearVal = document.getElementById('yearSelect').value;
            const monthVal = document.getElementById('monthSelect').value;
            const container = document.getElementById('filteredReportContainer');
            container.innerHTML = '';

            if(Object.keys(globalTree).length === 0) {
                container.innerHTML = '<div class="text-center py-16 bg-slate-900/40 rounded-3xl border border-slate-800 text-slate-400 text-sm font-bold">لا توجد حركات مسجلة حتى الآن.</div>';
                return;
            }

            let targetYears = yearVal === 'all' ? Object.keys(globalTree).sort().reverse() : [yearVal];

            targetYears.forEach(year => {
                const yData = globalTree[year];
                let targetMonths = monthVal === 'all' ? Object.keys(yData.months).sort().reverse() : [monthVal];

                targetMonths.forEach(month => {
                    if(!yData.months[month]) return;
                    const mData = yData.months[month];
                    const monthName = monthNames[month] || month;

                    ensureFridaysInMonth(year, month, mData);

                    const monthCard = document.createElement('div');
                    monthCard.className = "bg-slate-900/90 rounded-3xl border border-slate-800 overflow-hidden shadow-xl mb-4";

                    let rowsHTML = '';
                    mData.txs.sort((a, b) => new Date(b.date) - new Date(a.date));

                    mData.txs.forEach(tx => {
                        const dayName = getDayNameArabic(tx.date);
                        const badgeColor = tx.type === 'إيراد' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20';
                        rowsHTML += `
                            <tr class="hover:bg-slate-950/50 transition">
                                <td class="p-3.5 text-slate-300 font-bold">${dayName} ${tx.date}</td>
                                <td class="p-3.5"><span class="px-3 py-1 rounded-xl font-black ${badgeColor}">${tx.type}</span></td>
                                <td class="p-3.5 font-black text-white text-sm">${tx.amount.toLocaleString()}</td>
                                <td class="p-3.5 text-slate-400">${tx.description || '-'}</td>
                                <td class="p-3.5 text-center space-x-2 space-x-reverse">
                                    <button onclick="editTransaction('${tx.id}', '${tx.date}', '${tx.type}', ${tx.amount}, '${tx.description || ''}')" class="text-indigo-400 hover:text-indigo-300 hover:bg-indigo-500/10 p-2 rounded-xl transition text-xs font-bold cursor-pointer">✏️ تعديل</button>
                                    <button onclick="deleteTransaction('${tx.id}')" class="text-rose-500 hover:text-rose-400 hover:bg-rose-500/10 p-2 rounded-xl transition text-xs font-bold cursor-pointer">🗑️ حذف</button>
                                </td>
                            </tr>
                        `;
                    });

                    monthCard.innerHTML = `
                        <div onclick="toggleDetails(this)" class="bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 p-5 flex flex-wrap justify-between items-center gap-3 cursor-pointer hover:bg-slate-800/80 transition border-b border-slate-800">
                            <div class="flex items-center gap-3">
                                <span class="text-indigo-400 font-black text-lg">📅</span>
                                <div>
                                    <h4 class="font-black text-white text-base">شهر ${monthName} - سنة ${year}</h4>
                                    <p class="text-xs text-slate-400 mt-0.5">اضغط هنا لعرض تفاصيل الحركات (${mData.txs.length} حركة)</p>
                                </div>
                            </div>
                            <div class="flex flex-wrap gap-3 text-xs font-bold items-center">
                                <span class="text-emerald-400 bg-emerald-950/50 px-3.5 py-1.5 rounded-xl border border-emerald-900">إيراد: ${mData.rev.toLocaleString()}</span>
                                <span class="text-rose-400 bg-rose-950/50 px-3.5 py-1.5 rounded-xl border border-rose-900">مصروف: ${mData.exp.toLocaleString()}</span>
                                <span class="text-blue-400 font-black bg-blue-950/50 px-3.5 py-1.5 rounded-xl border border-blue-900">الصافي: ${mData.net.toLocaleString()}</span>
                                <span class="text-indigo-400 font-bold mr-2">▼ التفاصيل</span>
                            </div>
                        </div>
                        <div class="details-content hidden bg-slate-950/80 p-4 overflow-x-auto border-t border-slate-800">
                            <table class="w-full text-right text-xs">
                                <thead class="text-slate-400 font-bold border-b border-slate-800">
                                    <tr>
                                        <th class="p-3">التاريخ واليوم</th>
                                        <th class="p-3">النوع</th>
                                        <th class="p-3">المبلغ</th>
                                        <th class="p-3">البيان / الوصف</th>
                                        <th class="p-3 text-center">إجراءات</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-900 text-slate-300">
                                    ${rowsHTML}
                                </tbody>
                            </table>
                        </div>
                    `;

                    container.appendChild(monthCard);
                });
            });
        }

        function ensureFridaysInMonth(year, month, mData) {
            const today = new Date();
            const yearNum = parseInt(year);
            const monthNum = parseInt(month);
            const daysInMonth = new Date(yearNum, monthNum, 0).getDate();

            for (let day = 1; day <= daysInMonth; day++) {
                const dayStr = day < 10 ? '0' + day : '' + day;
                const dateString = `${year}-${month}-${dayStr}`;
                const checkDate = new Date(dateString);

                if (checkDate.getDay() === 5 && checkDate <= today) {
                    const exists = mData.txs.some(tx => tx.date === dateString);
                    if (!exists) {
                        mData.txs.push({
                            id: 'auto_fri_' + dateString,
                            date: dateString,
                            type: 'إيراد',
                            amount: 0.0,
                            description: 'إجازة',
                            isAuto: true
                        });
                    }
                }
            }
        }

        function toggleDetails(headerElem) {
            const content = headerElem.nextElementSibling;
            content.classList.toggle('hidden');
        }

        function editTransaction(id, date, type, amount, description) {
            if(id.startsWith('auto_fri_')) return;
            document.getElementById('editId').value = id;
            document.getElementById('date').value = date;
            document.getElementById('type').value = type;
            document.getElementById('amount').value = amount;
            document.getElementById('description').value = description;
            
            document.getElementById('formTitle').innerText = "تعديل الحركة المالية";
            document.getElementById('submitBtn').innerText = "تحديث البيانات في القاعدة";
            document.getElementById('cancelEditBtn').classList.remove('hidden');
            
            switchTab('input');
        }

        function resetForm() {
            document.getElementById('editId').value = '';
            document.getElementById('txForm').reset();
            document.getElementById('date').value = new Date().toISOString().split('T')[0];
            document.getElementById('formTitle').innerText = "تسجيل حركة مالية جديدة";
            document.getElementById('submitBtn').innerText = "حفظ في قاعدة البيانات";
            document.getElementById('cancelEditBtn').classList.add('hidden');
            document.getElementById('msg').classList.add('hidden');
        }

        async function deleteTransaction(id) {
            if(id.startsWith('auto_fri_')) return;
            const res = await fetch('/delete/' + id, { method: 'DELETE' });
            const result = await res.json();
            if(result.status === 'success') {
                loadReport();
            }
        }

        function exportToCSV() {
            let csv = 'اليوم والتاريخ,النوع,المبلغ,البيان\n';
            globalTransactions.forEach(tx => {
                const dayName = getDayNameArabic(tx.date);
                csv += `${dayName} ${tx.date},${tx.type},${tx.amount},"${tx.description || ''}"\n`;
            });
            const blob = new Blob(["\ufeff" + csv], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'Financial_Report_Turki.csv';
            a.click();
        }

        document.getElementById('txForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const editId = document.getElementById('editId').value;
            const payload = {
                date: document.getElementById('date').value,
                type: document.getElementById('type').value,
                amount: parseFloat(document.getElementById('amount').value),
                description: document.getElementById('description').value
            };

            const endpoint = editId ? '/update/' + editId : '/add';
            const method = editId ? 'PUT' : 'POST';

            const res = await fetch(endpoint, {
                method: method,
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            const result = await res.json();
            
            const msg = document.getElementById('msg');
            msg.classList.remove('hidden');
            if(result.status === 'success') {
                msg.className = "mt-4 p-4 rounded-2xl text-center text-sm font-black bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
                msg.innerText = editId ? "تم تحديث الحركة بنجاح!" : "تم حفظ الحركة في قاعدة البيانات بنجاح!";
                resetForm();
                loadReport();
                switchTab('reports');
            } else {
                msg.className = "mt-4 p-4 rounded-2xl text-center text-sm font-black bg-rose-500/10 text-rose-400 border border-rose-500/20";
                msg.innerText = "حدث خطأ أثناء الحفظ.";
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/report', methods=['GET'])
def api_report():
    try:
        docs = db.collection('transactions').stream()
        transactions = []
        total_rev = 0.0
        total_exp = 0.0

        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            amt = float(d.get('amount', 0))
            d['amount'] = amt
            transactions.append(d)
            if d.get('type') == 'إيراد':
                total_rev += amt
            else:
                total_exp += amt

        net = total_rev - total_exp
        return jsonify({
            'status': 'success',
            'transactions': transactions,
            'total_revenue': total_rev,
            'total_expense': total_exp,
            'net': net
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/add', methods=['POST'])
def add_transaction():
    try:
        data = request.json
        db.collection('transactions').add({
            'date': data.get('date'),
            'type': data.get('type'),
            'amount': float(data.get('amount', 0)),
            'description': data.get('description', ''),
            'created_at': datetime.utcnow()
        })
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/update/<tx_id>', methods=['PUT'])
def update_transaction(tx_id):
    try:
        data = request.json
        db.collection('transactions').document(tx_id).update({
            'date': data.get('date'),
            'type': data.get('type'),
            'amount': float(data.get('amount', 0)),
            'description': data.get('description', '')
        })
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/delete/<tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    try:
        db.collection('transactions').document(tx_id).delete()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)