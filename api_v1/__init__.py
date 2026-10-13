from fastapi import APIRouter

from .analytics.views import router as analytics_router
from .auth.views import router as auth_router
from .role.views import router as role_router
from .profile.views import router as profile_router
from .course.views import router as course_router
from .course_material.views import router as course_material_router
from .course_section.views import router as course_section_router
from .course_request.views import invitations_router, router as course_request_router
from .course_test.views import router as test_router
from .notification.views import router as notification_router
from .test_progress.views import router as test_progress_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth")
router.include_router(role_router, prefix="/role")
router.include_router(profile_router, prefix="/profile")
router.include_router(course_router, prefix="/course")
router.include_router(course_material_router, prefix="/course")
router.include_router(course_section_router, prefix="/course")
router.include_router(course_request_router, prefix="/course")
router.include_router(analytics_router, prefix="/course")
router.include_router(invitations_router, prefix="/invitations")
router.include_router(test_router, prefix="/tests")
router.include_router(test_progress_router, prefix="/test-progress")
router.include_router(notification_router, prefix="/notifications")
