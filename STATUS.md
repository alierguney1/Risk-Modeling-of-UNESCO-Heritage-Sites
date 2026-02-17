# UNESCO Heritage Sites Risk Modeling - Uygulama Durum Takibi

> **Proje**: Avrupa UNESCO Dünya Mirası Sitelerinin Risk Modellemesi  
> **Kapsam**: ~500+ UNESCO sitesi  
> **Altyapı**: PostgreSQL/PostGIS + Airflow  
> **Son Güncelleme**: 17 Şubat 2026

---

## 📊 Genel Durum Özeti

| Durum | Simge | Açıklama |
|-------|-------|----------|
| Tamamlandı | ✅ | Faz tamamlandı ve test edildi |
| Devam Ediyor | 🔄 | Faz üzerinde çalışılıyor |
| Beklemede | ⬜ | Faz henüz başlanmadı |
| Hatalı | ❌ | Faz hatalarla karşılaştı |

---

## 🎯 Faz Durumu (Phase Status)

### ✅ Faz 0 — Ortam Kurulumu ve Gereksinimler _(Tamamlandı)_

**Durum**: TAMAMLANDI  
**Tarih**: Gün 1-2

#### Tamamlanan İşler:
- [x] Python 3.10+ kurulumu
- [x] PostgreSQL + PostGIS kurulumu
- [x] `requirements.txt` dosyası oluşturuldu
- [x] `.env.example` şablon dosyası hazırlandı
- [x] Proje bağımlılıkları tanımlandı

#### Test Komutları:
```bash
# Python versiyonunu kontrol et
python --version  # 3.10+ olmalı

# PostgreSQL versiyonunu kontrol et
psql --version  # 14+ önerilir

# PostGIS kurulumunu kontrol et
psql -U postgres -c "SELECT PostGIS_Version();"

# Bağımlılıkları yükle
pip install -r requirements.txt

# Kurulu paketleri listele
pip list | grep -E "geopandas|osmnx|folium|sqlalchemy"
```

#### Çıktı Örneği:
```
geopandas      0.14.x
osmnx          1.9.x
folium         0.15.x
sqlalchemy     2.0.x
```

---

### ✅ Faz 1 — Proje İskeleti ve Yapılandırma _(Tamamlandı)_

**Durum**: TAMAMLANDI  
**Tarih**: Gün 2-3

#### Tamamlanan İşler:
- [x] Dizin yapısı oluşturuldu (`src/`, `config/`, `sql/`, `tests/`)
- [x] `config/settings.py` yapılandırma dosyası hazırlandı
- [x] Sabitler tanımlandı (CRS, API URLs, risk weights)
- [x] Avrupa ISO kodları listelendi
- [x] `setup.py` paket yapılandırması oluşturuldu

#### Test Komutları:
```bash
# Dizin yapısını kontrol et
tree -L 2 -d

# Yapılandırma dosyasını kontrol et
python -c "from config.settings import *; print(f'Database: {POSTGRES_DB}'); print(f'Europe Countries: {len(EUROPE_ISO_CODES)}')"

# İçe aktarmaları test et
python -c "import src; print('✓ src package imported')"
python -c "from config import settings; print('✓ settings imported')"
```

#### Beklenen Çıktı:
```
Database: unesco_risk
Europe Countries: 50
✓ src package imported
✓ settings imported
```

---

### ✅ Faz 2 — Veritabanı Katmanı _(Tamamlandı)_

**Durum**: TAMAMLANDI  
**Tarih**: Gün 3-5

#### Tamamlanan İşler:
- [x] SQL şema dosyaları oluşturuldu
  - [x] `01_create_schema.sql` — `unesco_risk` şeması
  - [x] `02_create_tables.sql` — 7 tablo tanımı
  - [x] `03_create_indices.sql` — Mekansal indeksler
- [x] SQLAlchemy ORM modelleri oluşturuldu (`src/db/models.py`)
- [x] Veritabanı bağlantı modülü (`src/db/connection.py`)
- [x] GeoAlchemy2 entegrasyonu

#### Tablolar:
1. `heritage_sites` — UNESCO siteleri
2. `urban_features` — OSM kentsel özellikler
3. `climate_events` — İklim olayları
4. `earthquake_events` — Deprem verileri
5. `fire_events` — Yangın olayları
6. `flood_zones` — Sel bölgeleri
7. `risk_scores` — Risk skorları

#### Test Komutları:
```bash
# .env dosyasını oluştur (eğer yoksa)
cp .env.example .env
# .env dosyasını düzenle ve veritabanı bilgilerini gir

# PostgreSQL veritabanını oluştur
createdb -U postgres unesco_risk

# PostGIS uzantısını etkinleştir
psql -U postgres -d unesco_risk -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# SQL şema dosyalarını çalıştır
psql -U postgres -d unesco_risk -f sql/01_create_schema.sql
psql -U postgres -d unesco_risk -f sql/02_create_tables.sql
psql -U postgres -d unesco_risk -f sql/03_create_indices.sql

# Şema ve tabloları kontrol et
psql -U postgres -d unesco_risk -c "\dt unesco_risk.*"

# Mekansal indeksleri kontrol et
psql -U postgres -d unesco_risk -c "SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'unesco_risk';"

# ORM modellerini test et
python -c "from src.db.models import HeritageSite, UrbanFeature, ClimateEvent; print('✓ All models imported')"

# Veritabanı bağlantısını test et
python -c "from src.db.connection import engine, get_session; session = get_session(); print('✓ Database connection successful'); session.close()"
```

#### Beklenen Çıktı:
```
                  List of relations
   Schema    |       Name        | Type  |  Owner   
-------------+-------------------+-------+----------
 unesco_risk | heritage_sites    | table | postgres
 unesco_risk | urban_features    | table | postgres
 unesco_risk | climate_events    | table | postgres
 unesco_risk | earthquake_events | table | postgres
 unesco_risk | fire_events       | table | postgres
 unesco_risk | flood_zones       | table | postgres
 unesco_risk | risk_scores       | table | postgres
```

---

### 🔄 Faz 3 — Temel ETL: UNESCO Miras Siteleri _(Devam Ediyor)_

**Durum**: DEVAM EDİYOR  
**Tarih**: Gün 5-7  
**Hedef**: ~500 Avrupa UNESCO sitesini veritabanına yüklemek

#### Tamamlanacak İşler:
- [ ] `src/etl/fetch_unesco.py` modülü oluşturulacak
- [ ] UNESCO API'den veri çekilecek
- [ ] XML/JSON verisi parse edilecek
- [ ] Avrupa filtrelemesi (EUROPE_ISO_CODES)
- [ ] PostGIS'e kayıt edilecek
- [ ] Hata yönetimi ve loglama eklenecek
- [ ] İlerleme çubuğu (tqdm) eklenecek

#### Bekleyen Test Komutları:
```bash
# UNESCO veri çekme modülünü çalıştır
python -m src.etl.fetch_unesco

# Veritabanındaki site sayısını kontrol et
psql -U postgres -d unesco_risk -c "SELECT COUNT(*) FROM unesco_risk.heritage_sites;"

# Ülke dağılımını kontrol et
psql -U postgres -d unesco_risk -c "SELECT country, COUNT(*) FROM unesco_risk.heritage_sites GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10;"

# Kategori dağılımını kontrol et
psql -U postgres -d unesco_risk -c "SELECT category, COUNT(*) FROM unesco_risk.heritage_sites GROUP BY category;"

# Örnek site verilerini görüntüle
psql -U postgres -d unesco_risk -c "SELECT whc_id, name, country, category FROM unesco_risk.heritage_sites LIMIT 5;"

# Mekansal veri kontrolü
psql -U postgres -d unesco_risk -c "SELECT name, ST_AsText(geom) FROM unesco_risk.heritage_sites LIMIT 3;"
```

#### Beklenen Çıktı (Tamamlandığında):
```
 count 
-------
   500+

Top 10 Countries:
  country  | count
-----------+-------
 Italy     |   58
 Spain     |   49
 France    |   45
 Germany   |   51
 ...

Categories:
  category  | count
------------+-------
 Cultural   |   400+
 Natural    |    70+
 Mixed      |    30+
```

---

### ⬜ Faz 4 — ETL: Tehlike ve Çevre Verileri _(Beklemede)_

**Durum**: BEKLEMEDE (Faz 3'e bağımlı)  
**Tarih**: Gün 7-14

#### Alt Fazlar (Paralel Geliştirilebilir):

##### 4A — OSM Kentsel Özellikler
- [ ] `src/etl/fetch_osm.py` oluştur
- [ ] Her site için 5km yarıçapında OSM verisi çek
- [ ] Bina, arazi kullanımı verilerini kaydet

##### 4B — İklim Verileri
- [ ] `src/etl/fetch_climate.py` oluştur
- [ ] Open-Meteo API entegrasyonu
- [ ] NASA POWER API entegrasyonu
- [ ] 2020-2025 zaman serisi verileri

##### 4C — Deprem Verileri
- [ ] `src/etl/fetch_earthquake.py` oluştur
- [ ] USGS Earthquake API entegrasyonu
- [ ] Magnitude 3.0+ olayları

##### 4D — Yangın Verileri
- [ ] `src/etl/fetch_fire.py` oluştur
- [ ] NASA FIRMS API entegrasyonu
- [ ] Son 10 gün yangın tespitleri

##### 4E — Sel ve Yükseklik Verileri
- [ ] `src/etl/fetch_flood.py` oluştur
- [ ] `src/etl/fetch_elevation.py` oluştur
- [ ] GFMS ve OpenTopography API entegrasyonu

#### Test Komutları (Her Alt Faz İçin):
```bash
# OSM verilerini kontrol et
psql -U postgres -d unesco_risk -c "SELECT COUNT(*) FROM unesco_risk.urban_features;"

# İklim olaylarını kontrol et
psql -U postgres -d unesco_risk -c "SELECT COUNT(*) FROM unesco_risk.climate_events;"

# Deprem olaylarını kontrol et
psql -U postgres -d unesco_risk -c "SELECT COUNT(*) FROM unesco_risk.earthquake_events;"

# Yangın olaylarını kontrol et
psql -U postgres -d unesco_risk -c "SELECT COUNT(*) FROM unesco_risk.fire_events;"

# Sel bölgelerini kontrol et
psql -U postgres -d unesco_risk -c "SELECT COUNT(*) FROM unesco_risk.flood_zones;"
```

---

### ⬜ Faz 5 — CRS Dönüşümü ve Mekansal Birleştirme _(Beklemede)_

**Durum**: BEKLEMEDE (Faz 4'e bağımlı)  
**Tarih**: Gün 14-16

#### Tamamlanacak İşler:
- [ ] `src/etl/spatial_join.py` oluştur
- [ ] WGS84 → ETRS89/LAEA dönüşümü
- [ ] Mekansal mesafe hesaplamaları
- [ ] Buffer analizi (5km, 10km, 25km, 50km)

#### Test Komutları:
```bash
# Mekansal birleştirme işlemini çalıştır
python -m src.etl.spatial_join

# Mesafe hesaplamalarını kontrol et
psql -U postgres -d unesco_risk -c "SELECT AVG(distance_to_site_m), MAX(distance_to_site_m) FROM unesco_risk.urban_features WHERE distance_to_site_m IS NOT NULL;"
```

---

### ⬜ Faz 6 — Risk Skorlama Motoru _(Beklemede)_

**Durum**: BEKLEMEDE (Faz 5'e bağımlı)  
**Tarih**: Gün 16-20

#### Tamamlanacak İşler:
- [ ] `src/analysis/risk_scoring.py` oluştur
- [ ] Yakınlık Risk Skoru algoritması
- [ ] 6 risk kategorisi hesaplaması:
  - Kentsel yoğunluk riski
  - İklim anomalisi riski
  - Sismik risk
  - Yangın riski
  - Sel riski
  - Kıyı riski
- [ ] Kompozit risk skoru hesaplama

#### Test Komutları:
```bash
# Risk skorlarını hesapla
python -m src.analysis.risk_scoring

# Risk skorlarını kontrol et
psql -U postgres -d unesco_risk -c "SELECT COUNT(*) FROM unesco_risk.risk_scores;"

# Risk seviyesi dağılımı
psql -U postgres -d unesco_risk -c "SELECT risk_level, COUNT(*) FROM unesco_risk.risk_scores GROUP BY risk_level;"

# En yüksek riskli siteleri listele
psql -U postgres -d unesco_risk -c "SELECT hs.name, rs.composite_risk_score, rs.risk_level FROM unesco_risk.heritage_sites hs JOIN unesco_risk.risk_scores rs ON hs.id = rs.site_id ORDER BY rs.composite_risk_score DESC LIMIT 10;"
```

---

### ⬜ Faz 7 — Anomali Tespiti ve Yoğunluk Analizi _(Beklemede)_

**Durum**: BEKLEMEDE (Faz 6'ya bağımlı)  
**Tarih**: Gün 20-23

#### Tamamlanacak İşler:
- [ ] `src/analysis/anomaly_detection.py` oluştur
- [ ] `src/analysis/density_analysis.py` oluştur
- [ ] Isolation Forest modeli
- [ ] Kernel Density Estimation (KDE)

#### Test Komutları:
```bash
# Anomali tespitini çalıştır
python -m src.analysis.anomaly_detection

# Anomalileri kontrol et
psql -U postgres -d unesco_risk -c "SELECT COUNT(*) FROM unesco_risk.risk_scores WHERE is_anomaly = TRUE;"

# Anomali sitelerini listele
psql -U postgres -d unesco_risk -c "SELECT hs.name, rs.isolation_forest_score FROM unesco_risk.heritage_sites hs JOIN unesco_risk.risk_scores rs ON hs.id = rs.site_id WHERE rs.is_anomaly = TRUE;"
```

---

### ⬜ Faz 8 — Folium Görselleştirme _(Beklemede)_

**Durum**: BEKLEMEDE (Faz 7'ye bağımlı)  
**Tarih**: Gün 23-26

#### Tamamlanacak İşler:
- [ ] `src/visualization/folium_map.py` oluştur
- [ ] İnteraktif harita oluşturma
- [ ] Risk seviyesine göre renklendirme
- [ ] Popup bilgileri
- [ ] Harita katmanları (sites, hazards, density)

#### Test Komutları:
```bash
# Harita oluştur
python -m src.visualization.folium_map

# Çıktı dosyasını kontrol et
ls -lh output/maps/

# Haritayı tarayıcıda aç
xdg-open output/maps/europe_risk_map.html  # Linux
# veya
open output/maps/europe_risk_map.html      # macOS
```

---

### ⬜ Faz 9 — Airflow DAG Entegrasyonu _(Beklemede)_

**Durum**: BEKLEMEDE (Faz 8'e bağımlı)  
**Tarih**: Gün 26-30

#### Tamamlanacak İşler:
- [ ] `dags/` dizini oluştur
- [ ] `dags/unesco_risk_dag.py` oluştur
- [ ] Tüm ETL ve analiz adımlarını DAG'a ekle
- [ ] Zamanlama yapılandırması
- [ ] Hata bildirimleri

#### Test Komutları:
```bash
# Airflow başlat
airflow db init
airflow webserver -p 8080 &
airflow scheduler &

# DAG'ı kontrol et
airflow dags list | grep unesco

# DAG'ı test et
airflow dags test unesco_risk_dag 2026-02-17

# DAG'ı tetikle
airflow dags trigger unesco_risk_dag

# Airflow UI'ı aç
# http://localhost:8080
```

---

### ⬜ Faz 10 — Test ve Kalite Güvencesi _(Beklemede)_

**Durum**: BEKLEMEDE (Faz 9'a bağımlı)  
**Tarih**: Gün 30-35

#### Tamamlanacak İşler:
- [ ] Birim testleri genişlet
- [ ] Entegrasyon testleri ekle
- [ ] Jupyter notebook'ları oluştur
- [ ] README.md güncelle
- [ ] Dokümantasyon tamamla

#### Test Komutları:
```bash
# Tüm testleri çalıştır
pytest tests/ -v

# Belirli bir test dosyasını çalıştır
pytest tests/test_db.py -v
pytest tests/test_etl.py -v

# Test kapsamını kontrol et
pytest --cov=src tests/

# Jupyter notebook'u başlat
jupyter notebook notebooks/
```

---

## 🚀 Hızlı Başlangıç Kılavuzu

### 1. İlk Kurulum

```bash
# Repository'i klonla (eğer daha önce yapılmadıysa)
git clone https://github.com/alierguney1/Risk-Modeling-of-UNESCO-Heritage-Sites.git
cd Risk-Modeling-of-UNESCO-Heritage-Sites

# Sanal ortam oluştur
python -m venv venv
source venv/bin/activate  # Linux/macOS
# veya
venv\Scripts\activate     # Windows

# Bağımlılıkları yükle
pip install -r requirements.txt

# .env dosyasını oluştur
cp .env.example .env
# .env dosyasını düzenle ve veritabanı bilgilerini gir
```

### 2. Veritabanı Kurulumu

```bash
# PostgreSQL veritabanını oluştur
createdb -U postgres unesco_risk

# PostGIS uzantısını etkinleştir
psql -U postgres -d unesco_risk -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# Şema ve tabloları oluştur
psql -U postgres -d unesco_risk -f sql/01_create_schema.sql
psql -U postgres -d unesco_risk -f sql/02_create_tables.sql
psql -U postgres -d unesco_risk -f sql/03_create_indices.sql
```

### 3. Veritabanı Bağlantısını Test Et

```bash
python -c "from src.db.connection import engine, get_session; session = get_session(); print('✓ Veritabanı bağlantısı başarılı'); session.close()"
```

### 4. ETL İşlemlerini Çalıştır (Faz 3+ Tamamlandıktan Sonra)

```bash
# UNESCO sitelerini çek (Faz 3)
python -m src.etl.fetch_unesco

# OSM verilerini çek (Faz 4A)
python -m src.etl.fetch_osm

# İklim verilerini çek (Faz 4B)
python -m src.etl.fetch_climate

# Diğer veri kaynaklarını çek (Faz 4C-E)
python -m src.etl.fetch_earthquake
python -m src.etl.fetch_fire
python -m src.etl.fetch_flood
python -m src.etl.fetch_elevation

# Mekansal birleştirme (Faz 5)
python -m src.etl.spatial_join

# Risk skorlarını hesapla (Faz 6)
python -m src.analysis.risk_scoring

# Anomali tespiti (Faz 7)
python -m src.analysis.anomaly_detection

# Harita oluştur (Faz 8)
python -m src.visualization.folium_map
```

---

## 🔍 Veri Doğrulama Sorguları

### Genel Veri Sayıları
```sql
-- Tüm tabloların kayıt sayıları
SELECT 
    'heritage_sites' as table_name, COUNT(*) as count FROM unesco_risk.heritage_sites
UNION ALL
SELECT 'urban_features', COUNT(*) FROM unesco_risk.urban_features
UNION ALL
SELECT 'climate_events', COUNT(*) FROM unesco_risk.climate_events
UNION ALL
SELECT 'earthquake_events', COUNT(*) FROM unesco_risk.earthquake_events
UNION ALL
SELECT 'fire_events', COUNT(*) FROM unesco_risk.fire_events
UNION ALL
SELECT 'flood_zones', COUNT(*) FROM unesco_risk.flood_zones
UNION ALL
SELECT 'risk_scores', COUNT(*) FROM unesco_risk.risk_scores;
```

### UNESCO Siteleri Detayları
```sql
-- Ülke bazında site dağılımı
SELECT country, category, COUNT(*) 
FROM unesco_risk.heritage_sites 
GROUP BY country, category 
ORDER BY COUNT(*) DESC;

-- En eski ve en yeni siteler
SELECT name, country, date_inscribed 
FROM unesco_risk.heritage_sites 
WHERE date_inscribed IS NOT NULL 
ORDER BY date_inscribed ASC 
LIMIT 5;

-- Tehlike listesindeki siteler
SELECT name, country, category 
FROM unesco_risk.heritage_sites 
WHERE in_danger = TRUE;
```

### Risk Analizi Sorguları
```sql
-- Risk seviyesi dağılımı
SELECT risk_level, COUNT(*), 
       ROUND(AVG(composite_risk_score)::numeric, 3) as avg_score
FROM unesco_risk.risk_scores
GROUP BY risk_level
ORDER BY avg_score DESC;

-- En yüksek riskli 20 site
SELECT hs.name, hs.country, 
       rs.composite_risk_score,
       rs.urban_density_score,
       rs.seismic_risk_score,
       rs.fire_risk_score
FROM unesco_risk.heritage_sites hs
JOIN unesco_risk.risk_scores rs ON hs.id = rs.site_id
ORDER BY rs.composite_risk_score DESC
LIMIT 20;

-- Anomali siteleri
SELECT hs.name, hs.country, 
       rs.isolation_forest_score,
       rs.composite_risk_score
FROM unesco_risk.heritage_sites hs
JOIN unesco_risk.risk_scores rs ON hs.id = rs.site_id
WHERE rs.is_anomaly = TRUE;
```

---

## 📝 Notlar ve İpuçları

### Performans İpuçları
- OSM veri çekme işlemi yavaş olabilir (~42 dakika 500 site için)
- Paralel çalıştırmak için Faz 4 alt fazlarını ayrı terminal pencerelerinde başlatın
- İklim verileri büyük olabilir, sayfalama kullanın
- API rate limit'lerine dikkat edin (Overpass API: ~2 req/10s)

### Hata Ayıklama
```bash
# Loglama seviyesini artır
export LOG_LEVEL=DEBUG

# Veritabanı bağlantı sorunları için
psql -U postgres -d unesco_risk -c "SELECT version();"

# Mekansal veri sorunları için
psql -U postgres -d unesco_risk -c "SELECT PostGIS_Full_Version();"

# Python modül import sorunları için
python -c "import sys; print('\n'.join(sys.path))"
```

### Veri Yedekleme
```bash
# Veritabanını yedekle
pg_dump -U postgres -d unesco_risk -F c -f backup_$(date +%Y%m%d).dump

# Yedekten geri yükle
pg_restore -U postgres -d unesco_risk backup_20260217.dump
```

---

## 📞 Yardım ve Destek

### Sorun Bildirimi
Herhangi bir sorunla karşılaşırsanız:
1. Yukarıdaki test komutlarını çalıştırın
2. Hata mesajlarını ve logları toplayın
3. GitHub Issues'a detaylı açıklama ile bildirin

### Katkıda Bulunma
1. Bu repository'i fork edin
2. Yeni bir branch oluşturun (`git checkout -b feature/yeni-ozellik`)
3. Değişikliklerinizi commit edin
4. Branch'inizi push edin
5. Pull Request açın

---

## 📚 Ek Kaynaklar

- [PLAN.MD](./PLAN.MD) - Detaylı teknik mimari ve uygulama planı
- [README.md](./README.md) - Proje genel bakış
- [PostgreSQL Dokümantasyonu](https://www.postgresql.org/docs/)
- [PostGIS Dokümantasyonu](https://postgis.net/documentation/)
- [SQLAlchemy Dokümantasyonu](https://docs.sqlalchemy.org/)
- [UNESCO World Heritage Centre](https://whc.unesco.org/)

---

**Son Güncelleme**: 17 Şubat 2026  
**Versiyon**: 1.0  
**Aktif Faz**: Faz 3 (UNESCO ETL)
