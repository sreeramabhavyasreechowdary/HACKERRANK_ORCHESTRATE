"""Identity resolution module (Overrides 4).

Resolves current AND historical identifiers (user_identities.csv + user_audit_log.csv)
before matching any records in evidence.
"""

from typing import Dict, List, Set, Optional
import pandas as pd
from pydantic import BaseModel, Field


class ResolvedIdentity(BaseModel):
    """Complete identity cluster for a user across current and historical records."""
    user_id: str
    primary_email: str
    names: Set[str] = Field(default_factory=set)
    emails: Set[str] = Field(default_factory=set)
    email_hashes: Set[str] = Field(default_factory=set)
    phones: Set[str] = Field(default_factory=set)
    all_terms: Set[str] = Field(default_factory=set)


class IdentityResolver:
    """Indexes and resolves identities across user_identities.csv and user_audit_log.csv."""

    def __init__(self, identities_df: pd.DataFrame, audit_log_df: pd.DataFrame):
        self.identities_df = identities_df
        self.audit_log_df = audit_log_df
        self._build_index()

    def _build_index(self):
        # Index user_identities by email and user_id
        self.by_email: Dict[str, Dict] = {}
        self.by_user_id: Dict[str, Dict] = {}

        for _, row in self.identities_df.iterrows():
            r = row.to_dict()
            email = str(r.get("email", "")).strip().lower()
            uid = str(r.get("user_id", "")).strip()
            if email:
                self.by_email[email] = r
            if uid:
                self.by_user_id[uid] = r

        # Index audit log changes by user_id and old_value/new_value
        self.audit_by_user_id: Dict[str, List[Dict]] = {}
        self.audit_by_value: Dict[str, str] = {}  # value -> user_id

        for _, row in self.audit_log_df.iterrows():
            r = row.to_dict()
            uid = str(r.get("user_id", "")).strip()
            self.audit_by_user_id.setdefault(uid, []).append(r)

            old_v = str(r.get("old_value", "")).strip().lower()
            new_v = str(r.get("new_value", "")).strip().lower()
            if old_v and old_v != "nan":
                self.audit_by_value[old_v] = uid
            if new_v and new_v != "nan":
                self.audit_by_value[new_v] = uid

    def resolve(self, email: str) -> Optional[ResolvedIdentity]:
        """Resolve all current and historical identifiers for an email."""
        clean_email = email.strip().lower()

        # Find user record
        user_record = self.by_email.get(clean_email)
        user_id = None

        if user_record:
            user_id = str(user_record.get("user_id", "")).strip()
        elif clean_email in self.audit_by_value:
            user_id = self.audit_by_value[clean_email]
            user_record = self.by_user_id.get(user_id)

        if not user_record and not user_id:
            # Fallback if user profile not found in table
            return ResolvedIdentity(
                user_id="",
                primary_email=clean_email,
                emails={clean_email},
                all_terms={clean_email},
            )

        user_id = user_id or str(user_record.get("user_id", "")).strip()
        names = set()
        emails = {clean_email}
        email_hashes = set()
        phones = set()

        if user_record:
            name = str(user_record.get("name", "")).strip()
            if name and name != "nan":
                names.add(name)
            curr_email = str(user_record.get("email", "")).strip().lower()
            if curr_email and curr_email != "nan":
                emails.add(curr_email)
            ehash = str(user_record.get("email_hash", "")).strip().lower()
            if ehash and ehash != "nan":
                email_hashes.add(ehash)
            phone = str(user_record.get("phone", "")).strip()
            if phone and phone != "nan":
                phones.add(phone)

        # Incorporate audit log historical identity updates
        history = self.audit_by_user_id.get(user_id, [])
        for h in history:
            field = str(h.get("field_name", "")).strip().lower()
            old_val = str(h.get("old_value", "")).strip()
            new_val = str(h.get("new_value", "")).strip()

            for val in [old_val, new_val]:
                if not val or val == "nan":
                    continue
                if field == "email":
                    emails.add(val.lower())
                elif field == "email_hash":
                    email_hashes.add(val.lower())
                elif field == "phone":
                    phones.add(val)

        # Build combined search terms
        all_terms = set()
        if user_id:
            all_terms.add(user_id.lower())
        for n in names:
            all_terms.add(n.lower())
        for e in emails:
            all_terms.add(e.lower())
        for eh in email_hashes:
            all_terms.add(eh.lower())
        for p in phones:
            all_terms.add(p.lower())
            # Add unformatted phone digits
            digits = "".join(ch for ch in p if ch.isdigit())
            if len(digits) >= 7:
                all_terms.add(digits)

        return ResolvedIdentity(
            user_id=user_id,
            primary_email=clean_email,
            names=names,
            emails=emails,
            email_hashes=email_hashes,
            phones=phones,
            all_terms=all_terms,
        )
