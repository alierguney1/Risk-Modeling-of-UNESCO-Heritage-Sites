"""
Unit tests for UNESCO ETL module.
"""

import unittest
from unittest.mock import patch, MagicMock
from src.etl.fetch_unesco import (
    parse_xml_to_records,
    parse_json_to_records,
    filter_european_sites,
    validate_records,
    create_geodataframe
)


class TestUNESCOETL(unittest.TestCase):
    """Test cases for UNESCO ETL functions."""
    
    def setUp(self):
        """Set up test data."""
        self.sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<query>
    <row>
        <id_number>91</id_number>
        <site>Venice and its Lagoon</site>
        <category>Cultural</category>
        <date_inscribed>1987</date_inscribed>
        <states>Italy</states>
        <iso_code>IT</iso_code>
        <region>Europe and North America</region>
        <criteria_txt>(i)(ii)(iii)(iv)(v)(vi)</criteria_txt>
        <danger>0</danger>
        <area_hectares>7092.0</area_hectares>
        <latitude>45.4371908</latitude>
        <longitude>12.3345898</longitude>
        <short_description>Venice is extraordinary.</short_description>
    </row>
    <row>
        <id_number>94</id_number>
        <site>Historic Centre of Rome</site>
        <category>Cultural</category>
        <date_inscribed>1980</date_inscribed>
        <states>Italy,Vatican City State</states>
        <iso_code>IT,VA</iso_code>
        <region>Europe and North America</region>
        <criteria_txt>(i)(ii)(iii)(iv)(vi)</criteria_txt>
        <danger>0</danger>
        <area_hectares>1430.0</area_hectares>
        <latitude>41.8954656</latitude>
        <longitude>12.4823243</longitude>
        <short_description>Historic Centre of Rome.</short_description>
    </row>
</query>"""
        
        self.sample_records = [
            {
                'whc_id': 91,
                'name': 'Venice and its Lagoon',
                'category': 'Cultural',
                'date_inscribed': 1987,
                'country': 'Italy',
                'iso_code': 'IT',
                'region': 'Europe and North America',
                'criteria': '(i)(ii)(iii)(iv)(v)(vi)',
                'in_danger': False,
                'area_hectares': 7092.0,
                'description': 'Venice is extraordinary.',
                'latitude': 45.4371908,
                'longitude': 12.3345898,
            },
            {
                'whc_id': 94,
                'name': 'Historic Centre of Rome',
                'category': 'Cultural',
                'date_inscribed': 1980,
                'country': 'Italy,Vatican City State',
                'iso_code': 'IT,VA',
                'region': 'Europe and North America',
                'criteria': '(i)(ii)(iii)(iv)(vi)',
                'in_danger': False,
                'area_hectares': 1430.0,
                'description': 'Historic Centre of Rome.',
                'latitude': 41.8954656,
                'longitude': 12.4823243,
            },
            {
                'whc_id': 200,
                'name': 'Great Barrier Reef',
                'category': 'Natural',
                'date_inscribed': 1981,
                'country': 'Australia',
                'iso_code': 'AU',
                'region': 'Asia-Pacific',
                'criteria': '(vii)(viii)(ix)(x)',
                'in_danger': False,
                'area_hectares': 34870000.0,
                'description': 'Great Barrier Reef.',
                'latitude': -18.2871,
                'longitude': 147.6992,
            }
        ]
    
    def test_parse_xml_to_records(self):
        """Test XML parsing functionality."""
        records = parse_xml_to_records(self.sample_xml)
        
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['whc_id'], 91)
        self.assertEqual(records[0]['name'], 'Venice and its Lagoon')
        self.assertEqual(records[0]['category'], 'Cultural')
        self.assertEqual(records[1]['whc_id'], 94)
    
    def test_filter_european_sites(self):
        """Test that filter_european_sites (legacy) returns all records in global scope."""
        all_sites = filter_european_sites(self.sample_records)
        
        # Global scope: should return all sites including Australia
        self.assertEqual(len(all_sites), 3)
    
    def test_validate_records(self):
        """Test record validation."""
        valid, report = validate_records(self.sample_records)
        
        self.assertEqual(report['total_records'], 3)
        self.assertEqual(report['valid_records'], 3)
        self.assertEqual(report['invalid_records'], 0)
        self.assertEqual(len(report['duplicate_whc_ids']), 0)
    
    def test_validate_duplicate_detection(self):
        """Test duplicate WHC ID detection."""
        duplicate_records = self.sample_records + [self.sample_records[0]]
        valid, report = validate_records(duplicate_records)
        
        self.assertEqual(len(report['duplicate_whc_ids']), 1)
        self.assertEqual(report['duplicate_whc_ids'][0], 91)
    
    def test_create_geodataframe(self):
        """Test GeoDataFrame creation."""
        gdf = create_geodataframe(self.sample_records[:2])
        
        self.assertEqual(len(gdf), 2)
        self.assertTrue('geometry' in gdf.columns)
        self.assertEqual(gdf.crs.to_string(), 'EPSG:4326')
        self.assertTrue(gdf.geometry.is_valid.all())


if __name__ == '__main__':
    unittest.main()
