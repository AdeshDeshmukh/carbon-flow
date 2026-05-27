import pandas as pd
from datetime import datetime
from decimal import Decimal


UNIT_CONVERSIONS = {
    'GAL': {'to': 'L', 'factor': Decimal('3.78541')},
    'SCF': {'to': 'M3', 'factor': Decimal('0.0283168')},
    'miles': {'to': 'km', 'factor': Decimal('1.60934')},
}


EMISSION_FACTORS = {
    ('diesel', 'L', '1'): Decimal('2.698'),
    ('gasoline', 'L', '1'): Decimal('2.320'),
    ('natural_gas', 'SCF', '1'): Decimal('0.05444'),
    ('natural_gas', 'M3', '1'): Decimal('1.922'),
    ('propane', 'L', '1'): Decimal('1.511'),
    ('biodiesel', 'L', '1'): Decimal('2.497'),
    ('electricity_us_avg', 'kWh', '2'): Decimal('0.350'),
    ('flight_longhaul_economy', 'passenger-km', '3'): Decimal('0.200110'),
    ('flight_longhaul_business', 'passenger-km', '3'): Decimal('0.580290'),
    ('flight_shorthaul_economy', 'passenger-km', '3'): Decimal('0.182870'),
    ('flight_shorthaul_business', 'passenger-km', '3'): Decimal('0.274300'),
}


def normalize_unit(value, from_unit):
    value_decimal = Decimal(str(value))
    
    if from_unit in UNIT_CONVERSIONS:
        conversion = UNIT_CONVERSIONS[from_unit]
        normalized_value = value_decimal * conversion['factor']
        normalized_unit = conversion['to']
    else:
        normalized_value = value_decimal
        normalized_unit = from_unit
    
    return normalized_value, normalized_unit


def get_emission_factor(fuel_type, unit, scope):
    key = (fuel_type.lower(), unit, scope)
    return EMISSION_FACTORS.get(key, Decimal('0'))


def parse_date(date_str):
    formats = ['%Y%m%d', '%Y-%m-%d', '%m/%d/%Y', '%d.%m.%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(str(date_str), fmt).date()
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse date: {date_str}")


def determine_fuel_type(material_description):
    description_lower = material_description.lower()
    
    if 'diesel' in description_lower:
        return 'diesel'
    elif 'gasoline' in description_lower or 'petrol' in description_lower:
        return 'gasoline'
    elif 'natural gas' in description_lower or 'gas' in description_lower:
        return 'natural_gas'
    elif 'propane' in description_lower:
        return 'propane'
    elif 'biodiesel' in description_lower:
        return 'biodiesel'
    else:
        return 'unknown_fuel'


def parse_sap_csv(file_path, company, data_source, ingestion_job):
    df = pd.read_csv(file_path)
    
    required_columns = ['Material_Number', 'Material_Description', 'Posting_Date', 'Quantity', 'Unit']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    
    emissions = []
    errors = []
    
    for index, row in df.iterrows():
        try:
            quantity = float(row['Quantity'])
            unit = row['Unit'].strip()
            fuel_type = determine_fuel_type(row['Material_Description'])
            
            normalized_value, normalized_unit = normalize_unit(quantity, unit)
            
            emission_factor = get_emission_factor(fuel_type, normalized_unit, '1')
            co2e_kg = normalized_value * emission_factor
            
            activity_date = parse_date(row['Posting_Date'])
            
            emission_data = {
                'company': company,
                'data_source': data_source,
                'ingestion_job': ingestion_job,
                'scope': '1',
                'category': 'stationary_combustion',
                'activity_date': activity_date,
                'original_value': Decimal(str(quantity)),
                'original_unit': unit,
                'normalized_value': normalized_value,
                'normalized_unit': normalized_unit,
                'co2e_kg': co2e_kg,
                'status': 'pending',
                'raw_data': row.to_dict(),
            }
            
            emissions.append(emission_data)
            
        except Exception as e:
            errors.append({
                'row': index + 1,
                'error': str(e),
                'data': row.to_dict()
            })
    
    return emissions, errors


def parse_utility_csv(file_path, company, data_source, ingestion_job):
    df = pd.read_csv(file_path)
    
    required_columns = ['Meter_ID', 'Bill_Start_Date', 'Bill_End_Date', 'Usage_kWh']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    
    emissions = []
    errors = []
    
    for index, row in df.iterrows():
        try:
            usage_kwh = float(row['Usage_kWh'])
            
            normalized_value = Decimal(str(usage_kwh))
            normalized_unit = 'kWh'
            
            emission_factor = get_emission_factor('electricity_us_avg', 'kWh', '2')
            co2e_kg = normalized_value * emission_factor
            
            activity_date = parse_date(row['Bill_Start_Date'])
            
            emission_data = {
                'company': company,
                'data_source': data_source,
                'ingestion_job': ingestion_job,
                'scope': '2',
                'category': 'purchased_electricity',
                'activity_date': activity_date,
                'original_value': Decimal(str(usage_kwh)),
                'original_unit': 'kWh',
                'normalized_value': normalized_value,
                'normalized_unit': normalized_unit,
                'co2e_kg': co2e_kg,
                'status': 'pending',
                'raw_data': row.to_dict(),
            }
            
            emissions.append(emission_data)
            
        except Exception as e:
            errors.append({
                'row': index + 1,
                'error': str(e),
                'data': row.to_dict()
            })
    
    return emissions, errors


def parse_travel_csv(file_path, company, data_source, ingestion_job):
    df = pd.read_csv(file_path)
    
    required_columns = ['Type', 'Travel_Date']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    
    emissions = []
    errors = []
    
    for index, row in df.iterrows():
        try:
            segment_type = row['Type'].strip().lower()
            
            if segment_type != 'flight':
                continue
            
            distance_km = float(row.get('Distance_km', 0))
            cabin_class = row.get('Class', 'Economy').strip().lower()
            
            if distance_km >= 3700:
                if 'business' in cabin_class or 'first' in cabin_class:
                    fuel_type = 'flight_longhaul_business'
                else:
                    fuel_type = 'flight_longhaul_economy'
            else:
                if 'business' in cabin_class or 'first' in cabin_class:
                    fuel_type = 'flight_shorthaul_business'
                else:
                    fuel_type = 'flight_shorthaul_economy'
            
            normalized_value = Decimal(str(distance_km))
            normalized_unit = 'passenger-km'
            
            emission_factor = get_emission_factor(fuel_type, 'passenger-km', '3')
            co2e_kg = normalized_value * emission_factor
            
            activity_date = parse_date(row['Travel_Date'])
            
            emission_data = {
                'company': company,
                'data_source': data_source,
                'ingestion_job': ingestion_job,
                'scope': '3',
                'category': 'business_travel',
                'activity_date': activity_date,
                'original_value': Decimal(str(distance_km)),
                'original_unit': 'km',
                'normalized_value': normalized_value,
                'normalized_unit': normalized_unit,
                'co2e_kg': co2e_kg,
                'status': 'pending',
                'raw_data': row.to_dict(),
            }
            
            emissions.append(emission_data)
            
        except Exception as e:
            errors.append({
                'row': index + 1,
                'error': str(e),
                'data': row.to_dict()
            })
    
    return emissions, errors
