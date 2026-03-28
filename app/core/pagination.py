import math
from typing import Any, List
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession



class PagedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool



async def paginate(query, page: int, page_size: int, db: AsyncSession) -> PagedResponse:

    count_query = select(func.count()).select_from(query.subquery())
    
    total = (await db.execute(count_query)).scalar() or 0

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    
    items = result.scalars().all()

    pages = math.ceil(total / page_size) if total > 0 else 1

    return PagedResponse(
        items=list(items),
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        has_next = page < pages,
    )