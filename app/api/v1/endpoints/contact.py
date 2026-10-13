"""Public contact and inquiry submission endpoint for DeckPilotAI."""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/contact", tags=["contact"])
logger = logging.getLogger(__name__)

InquiryCategory = Literal[
    "general",
    "partnership",
    "feedback",
    "support",
    "investor",
]


class ContactInquiryRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120, description="Full name of sender")
    email: EmailStr = Field(..., description="Valid contact email address")
    company: str | None = Field(default="", max_length=150, description="Optional company or organization name")
    inquiry_type: InquiryCategory = Field(default="general", description="Category of the inquiry")
    message: str = Field(..., min_length=10, max_length=5000, description="Inquiry message body")
    honeypot: str | None = Field(default="", max_length=100, description="Spam protection honeypot")


class ContactInquiryResponse(BaseModel):
    status: str
    message: str


@router.post("", response_model=ContactInquiryResponse, status_code=status.HTTP_200_OK)
def submit_contact_inquiry(payload: ContactInquiryRequest) -> ContactInquiryResponse:
    """Accept and record contact inquiries from the public website."""
    # Honeypot detection: bots automatically fill hidden honeypot fields
    if payload.honeypot and payload.honeypot.strip():
        logger.warning(
            "Spam bot detected in contact form submission from email: %s",
            payload.email,
        )
        # Return success to not tip off the bot, but drop the submission
        return ContactInquiryResponse(
            status="success",
            message="Thank you for reaching out. Your message has been received.",
        )

    logger.info(
        "Received contact inquiry: name='%s', email='%s', company='%s', type='%s', length=%d",
        payload.full_name,
        payload.email,
        payload.company or "N/A",
        payload.inquiry_type,
        len(payload.message),
    )

    return ContactInquiryResponse(
        status="success",
        message="Thank you for reaching out to DeckPilotAI. Our team has received your message and will respond shortly.",
    )
