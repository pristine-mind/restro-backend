from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception → 500
        return Response(
            {"detail": "An unexpected error occurred.", "code": "internal_error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Add error code for frontend switch statements
    if isinstance(exc, ValueError):
        return Response(
            {"detail": str(exc), "code": "business_rule_violation"},
            status=status.HTTP_409_CONFLICT,
        )

    return response
