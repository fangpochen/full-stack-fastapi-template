import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Item, ItemCreate, ItemPublic, ItemsPublic, 
    ItemUpdate, Message, UserProjectPermission
)

router = APIRouter(prefix="/items", tags=["items"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@router.get("/", response_model=ItemsPublic)
def read_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    获取项目列表。
    - 超级用户可以看到所有项目
    - 普通用户只能看到自己有权限的项目（通过 UserProjectPermission 关联）
    """
    try:
        if current_user.is_superuser:
            # 管理员可以看到所有项目
            count_statement = select(func.count()).select_from(Item)
            count = session.exec(count_statement).one()
            statement = select(Item).offset(skip).limit(limit)
            items = session.exec(statement).all()
        else:
            # 普通用户只能看到有权限的项目
            # 1. 通过 UserProjectPermission 关联查询
            # 2. 包括用户自己创建的项目
            statement = (
                select(Item)
                .distinct()
                .where(
                    # 用户创建的项目 OR 用户有权限的项目
                    (Item.owner_id == current_user.id) | 
                    (Item.id.in_(
                        select(UserProjectPermission.item_id)
                        .where(UserProjectPermission.user_id == current_user.id)
                    ))
                )
                .offset(skip)
                .limit(limit)
            )
            items = session.exec(statement).all()
            
            # 计算总数
            count_statement = (
                select(func.count())
                .select_from(
                    select(Item)
                    .distinct()
                    .where(
                        (Item.owner_id == current_user.id) | 
                        (Item.id.in_(
                            select(UserProjectPermission.item_id)
                            .where(UserProjectPermission.user_id == current_user.id)
                        ))
                    )
                    .subquery()
                )
            )
            count = session.exec(count_statement).one()

        logger.debug(f'Found {count} items for user {current_user.id}')
        return ItemsPublic(data=items, count=count)
        
    except Exception as e:
        logger.error(f"Error retrieving items: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="获取项目列表失败"
        )


@router.get("/{id}", response_model=ItemPublic)
def read_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get item by ID.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return item


@router.post("/", response_model=ItemPublic)
def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    """
    Create new item.
    只有超级用户可以创建项目。
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="只有管理员可以创建项目")
        
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """
    Update an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{id}")
def delete_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")
