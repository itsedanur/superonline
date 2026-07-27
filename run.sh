#!/bin/bash
echo "=========================================================="
echo "🚀 Turkcell Superonline Müşteri Şikayet Analiz Paneli"
echo "=========================================================="
echo ""
echo "1. Python Bağımlılıkları ve Veri Seti Kontrol Ediliyor..."
python3 -c "import json, re; print('✅ Standart Python kütüphaneleri hazır.')"

echo ""
echo "2. Backend API ve Web Sunucusu Başlatılıyor..."
echo "🔗 Web Arayüzü: http://localhost:8080"
echo "----------------------------------------------------------"
python3 server.py
