from fastapi import APIRouter, Depends

import h3
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import RoleChecker, get_current_user
from app.modules.analytics.schemas import DemandPoint, DoctorStats, RegionDetail
from app.modules.appointments.models import Appointment, AppointmentStatus
from app.modules.audit.router import Actions, log
from app.modules.auth.models import User
from app.core.cache import cache_get, cache_set, CacheKeys

router = APIRouter(dependencies=[Depends(RoleChecker(["ADMIN"]))])



@router.get("/demand", response_model=list[DemandPoint])
async def get_demand(db: AsyncSession = Depends(get_db), current_user: User=Depends(get_current_user)):
    
    cached = await cache_get(CacheKeys.ANALYTICS_DEMAND)
    if cached:
        print("[CACHE HIT] analytics:demand")
        return [DemandPoint(**item) for item in cached]

    result = await db.execute(
        select(
            Appointment.h3_index,
            func.count().label("count")
        ).group_by(Appointment.h3_index)
    )

    rows = result.all()

    response = []
    for h3_index, count in rows:
        lat, lon = h3.cell_to_latlng(h3_index) 

        response.append(
            DemandPoint(
                h3_index=h3_index,
                count=count,
                center_lat=lat,
                center_lon=lon,
            )
        )

    await cache_set(
        CacheKeys.ANALYTICS_DEMAND,
        [p.model_dump() for p in response],
        ttl_seconds=300,
    )
    print("[CACHE SET] analytics:demand (300s)")

    await log(db=db, user_id=current_user.id, action=Actions.VIEW_ANALYTICS)
    return response



@router.get("/region/{h3_index}", response_model=list[RegionDetail])
async def get_region_detail(
    h3_index: str,
    db: AsyncSession = Depends(get_db),
    current_user: User=Depends(get_current_user)
):
    
    cache_key = CacheKeys.analytics_region(h3_index)
    cached = await cache_get(cache_key)
    if cached:
        print(f"[CACHE HIT] {cache_key}")
        return RegionDetail(**cached)

    neighbors = list(h3.k_ring(h3_index, 1))

    result = await db.execute(
        select(
            Appointment.h3_index,
            func.count().label("count")
        )
        .where(Appointment.h3_index.in_(neighbors))
        .group_by(Appointment.h3_index)
    )

    counts = {row[0]: row[1] for row in result.all()}
    
    neighbor_points = []
    for cell in neighbors:
        lat, lon = h3.cell_to_latlng(cell) 

        neighbor_points.append(
            DemandPoint(
                h3_index=cell,
                count=counts.get(cell, 0),
                center_lat=lat,
                center_lon=lon,
            )
        )

    detail = RegionDetail(
        h3_index=h3_index,
        count=counts.get(h3_index, 0),
        neighbors=neighbor_points,
    )

    await cache_set(cache_key, detail.model_dump(), ttl_seconds=300)
    print(f"[CACHE SET] {cache_key} (300s)")

    await log(db=db, user_id=current_user.id, action=Actions.VIEW_ANALYTICS)

    return detail



@router.get("/doctors", response_model=list[DoctorStats])
async def get_region_detail(db: AsyncSession = Depends(get_db),current_user: User=Depends(get_current_user)):

    cached = await cache_get(CacheKeys.ANALYTICS_DOCTORS)
    if cached:
        print("[CACHE HIT] analytics:doctors")
        return [DoctorStats(**item) for item in cached]


    result = await db.execute(
        select(
            Appointment.doctor_id,
            func.count().label("total"),
            func.sum(
                case((Appointment.status == AppointmentStatus.COMPLETED, 1),else_=0)
            ).label("completed"),
            func.sum(
                case((Appointment.status == AppointmentStatus.CANCELLED, 1), else_=0)
            ).label("cancelled"),
        ).group_by(Appointment.doctor_id)
    )

    rows = result.all()
    
    response = []
    for doctor_id, total, completed, cancelled in rows:
        completion_rate = (completed / total) if total > 0 else 0
 
        response.append(
            DoctorStats(
                doctor_id = doctor_id,
                total=total,
                completed = completed,
                cancelled = cancelled,
                completion_rate = completion_rate
            )
        )

    await cache_set(
        CacheKeys.ANALYTICS_DOCTORS,
        [s.model_dump() for s in response],
        ttl_seconds=300,
    )
    print("[CACHE SET] analytics:doctors (300s)")


    await log(db=db, user_id=current_user.id, action=Actions.VIEW_ANALYTICS)
    return response



