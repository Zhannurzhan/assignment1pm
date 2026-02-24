import h3
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Appointment

def convert_to_h3(lat: float, lon:float, resolution: int = 9) -> str:
    """
    Converts GPS coordinates into a unique H3 hexagonal string.
    This fulfills the 'Institutional Spatial Indexing' requirement.
    """
    try:
        return h3.latlng_to_cell(lat, lon, resolution)  # geo_to_h3 -> latlng_to_cell (h3 v4 API)
    except Exception as e:
        return "invalid_coords"
    
async def aggregate_by_h3(db: AsyncSession, h3_index: str):  
    """
    Groups appointments by H3 index to show healthcare demand per region.
    """
    query = (
        select(Appointment.h3_index, func.count(Appointment.id).label("count"))
        .where(Appointment.h3_index == h3_index)  # фильтрация по нужному региону
        .group_by(Appointment.h3_index)
    )

    result = await db.execute(query)
    return [{"h3_index": row[0], "count": row[1]} for row in result.all()]

def get_neighboring_hexes(h3_index: str, ring_size: int = 1):
    """
    Finds clinics in the immediate neighborhood of a patient.
    """
    return h3.grid_disk(h3_index, ring_size)  # k_ring -> grid_disk (h3 v4 API)

