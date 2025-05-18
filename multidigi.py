import os
import geopandas as gpd
import pandas as pd

# Constantes para cálculos
TARGET_CRS_METRIC = "EPSG:32614"  # UTM zone para la región de Guadalajara
TYPICAL_LANE_WIDTH = 3.25  # Metros, ancho típico de carril

def validate_multidigit_dynamic(sector_id, data_dir="."):
    """
    Valida dinámicamente si los segmentos marcados como MULTIDIGIT='Y' en STREETS_NAV
    cumplen con los criterios de HERE según los parámetros calculados.
    
    Args:
        sector_id (str): ID del sector a validar (ej. "4815075")
        data_dir (str): Directorio base donde se encuentran las carpetas STREETS_NAV y STREETS_NAMING_ADDRESSING
        
    Returns:
        dict: Resultados y estadísticas de la validación
    """
    # 1. Definir rutas a los archivos
    nav_path = os.path.join(data_dir, f"STREETS_NAV/SREETS_NAV_{sector_id}.geojson")
    if not os.path.exists(nav_path):
        nav_path = os.path.join(data_dir, f"STREETS_NAV/STREETS_NAV_{sector_id}.geojson")
        if not os.path.exists(nav_path):
            return {"error": f"No se encontró archivo NAV para sector {sector_id}"}

    naming_path = os.path.join(data_dir, f"STREETS_NAMING_ADDRESSING/SREETS_NAMING_ADDRESSING_{sector_id}.geojson")
    if not os.path.exists(naming_path):
        naming_path = os.path.join(data_dir, f"STREETS_NAMING_ADDRESSING/STREETS_NAMING_ADDRESSING_{sector_id}.geojson")
        if not os.path.exists(naming_path):
            return {"error": f"No se encontró archivo NAMING para sector {sector_id}"}

    # 2. Cargar datos (solo una vez para cada dataset)
    try:
        print(f"Cargando datos del sector {sector_id}...")
        gdf_nav = gpd.read_file(nav_path)
        gdf_naming = gpd.read_file(naming_path)
        
        # Verificar columnas requeridas
        if 'link_id' not in gdf_nav.columns or 'MULTIDIGIT' not in gdf_nav.columns:
            return {"error": "Columnas requeridas no encontradas en STREETS_NAV"}
            
        # 3. Reproyectar a CRS métrico para cálculos precisos
        print("Reproyectando a coordenadas métricas...")
        gdf_nav_metric = gdf_nav.to_crs(TARGET_CRS_METRIC)
        gdf_naming_metric = gdf_naming.to_crs(TARGET_CRS_METRIC)
        
        # 4. Preparar diccionario de geometrías métricas para NAMING_ADDRESSING
        naming_geom_by_link = {}
        for _, row in gdf_naming_metric.iterrows():
            link_id = row.get('link_id')
            if link_id and not row.geometry.is_empty:
                naming_geom_by_link[link_id] = row.geometry
        
        # 5. Inicializar contadores
        total = len(gdf_nav)
        md_yes = len(gdf_nav[gdf_nav['MULTIDIGIT'] == 'Y'])
        md_no = len(gdf_nav[gdf_nav['MULTIDIGIT'] == 'N'])
        match_yes = 0  # MULTIDIGIT='Y' y debería ser Y
        match_no = 0   # MULTIDIGIT='N' y debería ser N
        wrong_yes = 0  # MULTIDIGIT='Y' pero debería ser N
        wrong_no = 0   # MULTIDIGIT='N' pero debería ser Y
        errors = 0
        details = []
        
        # 6. Procesar cada link
        print(f"Procesando {total} links...")
        for idx, row in gdf_nav_metric.iterrows():
            link_id = row['link_id']
            multidigit_value = row.get('MULTIDIGIT')
            
            if multidigit_value not in ['Y', 'N']:
                continue
            
            try:
                # 6.1 Determinar longitud del separador desde la geometría
                separator_length = row.geometry.length
                
                # 6.2 Determinar tipo de separador basado en atributos
                separator_type = determine_separator_type(row)
                
                # 6.3 Calcular ancho y distancia entre calzadas
                separator_width, roadbed_distance = calculate_separator_dimensions(
                    link_id, row, gdf_nav_metric, separator_type
                )
                
                # 6.4 Evaluar si el segmento cumple criterios para MULTIDIGIT
                calculated_md = evaluate_multidigit_criteria(
                    separator_type, separator_width, separator_length, roadbed_distance
                )
                
                # 6.5 Comparar resultado calculado con valor en el dataset
                if multidigit_value == 'Y' and calculated_md:
                    match_yes += 1
                elif multidigit_value == 'N' and not calculated_md:
                    match_no += 1
                elif multidigit_value == 'Y' and not calculated_md:
                    wrong_yes += 1
                    details.append({
                        'link_id': link_id,
                        'type': 'Y->N',
                        'params': {
                            'separator_type': separator_type,
                            'separator_width': separator_width,
                            'separator_length': separator_length,
                            'roadbed_distance': roadbed_distance
                        }
                    })
                elif multidigit_value == 'N' and calculated_md:
                    wrong_no += 1
                    details.append({
                        'link_id': link_id,
                        'type': 'N->Y',
                        'params': {
                            'separator_type': separator_type,
                            'separator_width': separator_width,
                            'separator_length': separator_length,
                            'roadbed_distance': roadbed_distance
                        }
                    })
            
            except Exception as e:
                errors += 1
                continue
        
        # 7. Calcular estadísticas
        matches = match_yes + match_no
        mismatches = wrong_yes + wrong_no
        agreement_rate = (matches / total * 100) if total > 0 else 0
        
        # 8. Devolver resultados
        return {
            "sector": sector_id,
            "total_links": total,
            "multidigit_yes": md_yes,
            "multidigit_no": md_no,
            "matches_yes": match_yes,
            "matches_no": match_no,
            "mismatches_yes": wrong_yes,
            "mismatches_no": wrong_no,
            "agreement_rate": agreement_rate,
            "errors": errors,
            "details": details[:10]  # Limitar detalles para no saturar
        }
    
    except Exception as e:
        return {"error": f"Error procesando sector {sector_id}: {str(e)}"}

def determine_separator_type(nav_row):
    """
    Determina el tipo de separador basado en los atributos del link.
    
    Args:
        nav_row: Fila del GeoDataFrame con atributos del link
        
    Returns:
        str: Tipo de separador ('physical_barrier', 'vegetation', etc.)
    """
    # Convertir atributos a valores utilizables
    form_of_way = str(nav_row.get('FORM_OF_WAY', ''))
    
    try:
        func_class = int(nav_row.get('FUNC_CLASS', 5))
    except (ValueError, TypeError):
        func_class = 5  # Valor por defecto si no se puede convertir
    
    is_bridge = str(nav_row.get('BRIDGE', nav_row.get('BRIDGE_FG', 'N'))).upper() == 'Y'
    is_tunnel = str(nav_row.get('TUNNEL', nav_row.get('TUNNEL_FG', 'N'))).upper() == 'Y'
    
    # Decidir tipo de separador según jerarquía de atributos
    if is_bridge or is_tunnel:
        return 'physical_barrier'
    
    # Por FORM_OF_WAY
    if form_of_way in ['1', '2', 'Motorway', 'Multiple Carriageway', 'Dual Carriageway']:
        return 'physical_barrier'
    elif form_of_way in ['6', 'Divided Road']:
        return 'physical_barrier'
    elif form_of_way in ['4', 'Roundabout']:
        return 'vegetation'
    
    # Por FUNC_CLASS
    if func_class in [1, 2]:
        return 'physical_barrier'  # Autopistas/arterias principales
    elif func_class == 3:
        return 'vegetation'  # Arterias secundarias
    elif func_class in [4, 5]:
        return 'vegetation'  # Calles menores
    
    return 'none'  # Valor por defecto

def calculate_separator_dimensions(link_id, current_row, gdf_nav_metric, separator_type):
    """
    Calcula el ancho del separador y la distancia entre calzadas.
    Primero intenta encontrar el link paralelo, y si no lo encuentra usa estimaciones.
    
    Args:
        link_id: ID del link actual
        current_row: Fila del GeoDataFrame con datos del link actual
        gdf_nav_metric: GeoDataFrame completo con todos los links (en CRS métrico)
        separator_type: Tipo de separador ya determinado
        
    Returns:
        tuple: (separator_width, roadbed_distance)
    """
    # 1. Buscar link paralelo más cercano con mismo nombre de calle (si está disponible)
    parallel_link = find_best_parallel_link(link_id, current_row, gdf_nav_metric)
    
    if parallel_link is not None:
        # 2a. Calcular geométricamente si hay link paralelo
        roadbed_distance = current_row.geometry.distance(parallel_link.geometry)
        
        # Estimar ancho de calzadas
        current_lanes = estimate_lanes(current_row)
        parallel_lanes = estimate_lanes(parallel_link)
        
        current_half_width = current_lanes * TYPICAL_LANE_WIDTH / 2
        parallel_half_width = parallel_lanes * TYPICAL_LANE_WIDTH / 2
        
        # Estimar ancho del separador
        separator_width = max(0.1, roadbed_distance - (current_half_width + parallel_half_width))
        
    else:
        # 2b. Usar estimaciones basadas en atributos si no hay link paralelo
        func_class = get_func_class(current_row)
        separator_width = estimate_separator_width(separator_type, func_class)
        
        # Estimar roadbed_distance
        roadway_width = estimate_lanes(current_row) * TYPICAL_LANE_WIDTH
        roadbed_distance = separator_width + roadway_width
    
    return separator_width, roadbed_distance

def find_best_parallel_link(link_id, current_row, gdf_nav_metric):
    """
    Encuentra el mejor candidato a link paralelo.
    
    Args:
        link_id: ID del link actual
        current_row: Fila con datos del link actual
        gdf_nav_metric: GeoDataFrame con todos los links
        
    Returns:
        GeoSeries/None: Fila del link paralelo o None si no se encuentra
    """
    # Solo considerar otros links con MULTIDIGIT='Y'
    candidates = gdf_nav_metric[(gdf_nav_metric['link_id'] != link_id) & 
                              (gdf_nav_metric['MULTIDIGIT'] == 'Y')].copy()
    
    if candidates.empty:
        return None
    
    # Filtrar por nombre de calle si está disponible
    if 'ST_NAME' in gdf_nav_metric.columns:
        street_name = current_row.get('ST_NAME')
        if street_name:
            name_candidates = candidates[candidates['ST_NAME'] == street_name]
            if not name_candidates.empty:
                candidates = name_candidates
    
    # Calcular distancias desde la geometría actual a cada candidato
    if current_row.geometry is None or current_row.geometry.is_empty:
        return None # No se puede calcular distancia si la geometría actual es inválida

    # Asegurarse que las geometrías en candidates son válidas antes de calcular la distancia
    valid_candidates_geometry = candidates[candidates.geometry.is_valid & ~candidates.geometry.is_empty]
    if valid_candidates_geometry.empty:
        return None

    # Calcular la distancia de forma vectorizada
    distances = valid_candidates_geometry.geometry.distance(current_row.geometry)
    
    # Asignar las distancias calculadas de vuelta a los candidatos válidos.
    # Es importante manejar los índices si valid_candidates_geometry es un subconjunto.
    # Una forma segura es crear la columna en el DataFrame original de candidatos
    # y luego filtrar, o trabajar con el subconjunto.
    # Para simplicidad, si se trabaja con el subconjunto:
    candidates_with_distances = valid_candidates_geometry.copy()
    candidates_with_distances['distance'] = distances
    
    # Buscar el más cercano dentro del umbral (80m según documentación HERE)
    closest = candidates_with_distances[candidates_with_distances['distance'] <= 80].sort_values('distance')
    
    if not closest.empty:
        return closest.iloc[0] # Devuelve la fila completa del candidato más cercano
    
    return None

def estimate_lanes(row):
    """Estima el número de carriles basado en atributos disponibles"""
    # Intentar obtener número de carriles de varios campos posibles
    lanes = row.get('NUM_LANES', row.get('LANE_COUNT', row.get('LANE_COUNT_F', row.get('LANE_COUNT_R'))))
    
    try:
        lanes = int(lanes)
        if lanes < 1:
            lanes = 1
        return lanes
    except (ValueError, TypeError):
        # Estimar basado en FUNC_CLASS si no hay dato explícito de carriles
        func_class = get_func_class(row)
        if func_class in [1, 2]:
            return 2  # Autopistas/arterias principales
        elif func_class == 3:
            return 2  # Arterias secundarias
        else:
            return 1  # Calles locales

def get_func_class(row):
    """Obtiene FUNC_CLASS como número entero"""
    try:
        return int(row.get('FUNC_CLASS', 5))
    except (ValueError, TypeError):
        return 5  # Valor por defecto

def estimate_separator_width(separator_type, func_class):
    """Estima el ancho del separador basado en su tipo y la clase funcional"""
    if separator_type == 'physical_barrier':
        if func_class in [1, 2]:
            return 3.0  # Barreras más anchas en autopistas
        elif func_class == 3:
            return 2.0  # Medianas en arterias secundarias
        else:
            return 1.5  # Medianas en calles locales
    elif separator_type == 'vegetation':
        if func_class in [1, 2, 3]:
            return 2.5  # Camellones en arterias principales/secundarias
        else:
            return 1.5  # Camellones en calles menores
    elif separator_type == 'legal_barrier':
        return 0.5  # Separación pintada
    elif separator_type in ['elevated', 'rail', 'tram']:
        return 4.0  # Estructuras elevadas/rieles
    elif separator_type == 'walkway':
        return 1.5  # Aceras/camellones peatonales
    else:
        return 0.1  # Default mínimo

def evaluate_multidigit_criteria(separator_type, separator_width, separator_length, roadbed_distance):
    """
    Evalúa si un segmento cumple los criterios para ser MULTIDIGIT según HERE.
    
    Args:
        separator_type (str): Tipo de separador
        separator_width (float): Ancho del separador en metros
        separator_length (float): Longitud del segmento en metros
        roadbed_distance (float): Distancia entre calzadas en metros
        
    Returns:
        bool: True si cumple criterios para MULTIDIGIT='Y', False en caso contrario
    """
    # Criterio 1: Anulación visual (separador corto pero ancho)
    if separator_length < 100 and separator_width > 3:
        return True
    
    # Criterio 2: Separadores físicos/estructurales
    if separator_type in ['physical_barrier', 'legal_barrier', 'rail', 'elevated', 'tram', 'walkway']:
        if separator_width > 3 and separator_length > 40 and roadbed_distance <= 80:
            return True
    
    # Criterio 3: Separadores de vegetación
    if separator_type == 'vegetation':
        if separator_width > 3 and separator_length > 40 and roadbed_distance <= 80:
            return True
    
    return False

def run_validation(sector="4815078", data_dir="."):
    """
    Ejecuta la validación de un sector y muestra los resultados.
    
    Args:
        sector (str): ID del sector a validar
        data_dir (str): Directorio base para los datos
        
    Returns:
        dict: Resultados de la validación
    """
    print(f"Iniciando validación MULTIDIGIT para sector {sector}...")
    results = validate_multidigit_dynamic(sector, data_dir)
    
    if "error" in results:
        print(f"ERROR: {results['error']}")
        return results
    
    # Mostrar resultados
    print("\n=== RESULTADOS DE VALIDACIÓN MULTIDIGIT ===")
    print(f"Sector: {results['sector']}")
    print(f"Links totales: {results['total_links']}")
    print(f"Links con MULTIDIGIT='Y': {results['multidigit_yes']}")
    print(f"Links con MULTIDIGIT='N': {results['multidigit_no']}")
    
    print(f"\nLinks correctamente validados:")
    print(f"  - MULTIDIGIT='Y' y debería ser 'Y': {results['matches_yes']}")
    print(f"  - MULTIDIGIT='N' y debería ser 'N': {results['matches_no']}")
    
    print(f"\nLinks con discrepancias:")
    print(f"  - MULTIDIGIT='Y' pero debería ser 'N': {results['mismatches_yes']}")
    print(f"  - MULTIDIGIT='N' pero debería ser 'Y': {results['mismatches_no']}")
    
    print(f"\nTasa de concordancia: {results['agreement_rate']:.2f}%")
    print(f"Errores de procesamiento: {results['errors']}")
    
    # Mostrar ejemplos de discrepancias
    if results['details']:
        print("\n=== EJEMPLOS DE DISCREPANCIAS ===")
        for i, detail in enumerate(results['details']):
            print(f"{i+1}. Link ID: {detail['link_id']}, Tipo: {detail['type']}")
            params = detail['params']
            print(f"   - Tipo de separador: {params['separator_type']}")
            print(f"   - Ancho de separador: {params['separator_width']:.2f}m")
            print(f"   - Longitud: {params['separator_length']:.2f}m")
            print(f"   - Distancia entre calzadas: {params['roadbed_distance']:.2f}m")
    
    return results

if __name__ == "__main__":
    # Puedes especificar el directorio base donde están las carpetas STREETS_NAV y STREETS_NAMING_ADDRESSING
    # Si son directorios relativos desde donde se ejecuta el script, usar "."
    run_validation(sector="4815078", data_dir=".")
