"""Organization API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.database import get_db_session
from ....shared.db.repositories.organizations import OrganizationRepository
from ....shared.schemas.organization import OrganizationResponse, OrganizationUpdate
from ...auth.dependencies import AdminUser, CurrentUser

router = APIRouter()


@router.get("", response_model=OrganizationResponse)
async def get_organization(
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get current organization details.
    """
    org_repo = OrganizationRepository(db)
    org = await org_repo.get_by_id(auth.organization_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Get usage stats
    camera_count = await org_repo.get_camera_count(auth.organization_id)
    user_count = await org_repo.get_user_count(auth.organization_id)

    response = OrganizationResponse.model_validate(org)
    response.camera_count = camera_count
    response.user_count = user_count

    return response


@router.patch("", response_model=OrganizationResponse)
async def update_organization(
    request: OrganizationUpdate,
    auth: AdminUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update organization settings (admin only).
    """
    org_repo = OrganizationRepository(db)
    org = await org_repo.get_by_id(auth.organization_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Update fields
    if request.name is not None:
        org.name = request.name
    if request.settings is not None:
        org.settings = request.settings

    await org_repo.update(org)

    # Get usage stats
    camera_count = await org_repo.get_camera_count(auth.organization_id)
    user_count = await org_repo.get_user_count(auth.organization_id)

    response = OrganizationResponse.model_validate(org)
    response.camera_count = camera_count
    response.user_count = user_count

    return response
