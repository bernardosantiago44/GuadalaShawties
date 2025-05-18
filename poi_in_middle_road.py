from poi_locator import load_geojson, find_poi_in_csv

def is_poi_on_multidigit_road(features, csv_path, poi_id):
    """
    Dado un POI, retorna True si la carretera asociada es multidigit ("Y"), False si es "N".
    Arroja un error si el POI_ID no se encuentra en el CSV o si el link_id no se encuentra en el GeoJSON.
    """
    poi_info = find_poi_in_csv(csv_path, poi_id)
    if poi_info is None:
        raise ValueError(f"POI_ID {poi_id} no encontrado en el CSV.")
    link_id = poi_info["link_id"]
    for feature in features:
        if feature["properties"]["link_id"] == link_id:
            multidigit = feature["properties"].get("MULTIDIGIT", "N")
            return multidigit == "Y"
    raise ValueError(f"link_id {link_id} no encontrado en el GeoJSON.")

if __name__ == "__main__":
    # Ejemplo de uso
    geojson_file = "STREETS_NAV/SREETS_NAV_4815075.geojson"
    csv_file = "POIS.csv"
    poi_id_to_find = 1244439551  # Reemplaza con el POI_ID que deseas buscar
    features = load_geojson(geojson_file)

    try:
        is_multidigit = is_poi_on_multidigit_road(features, csv_file, poi_id_to_find)
        print(f"El POI_ID {poi_id_to_find} está en una carretera multidigit: {is_multidigit}")
    except ValueError as e:
        print(e)