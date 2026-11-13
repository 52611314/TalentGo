import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.profile import ProfilePatch


def test_database_configuration_rejects_other_ports():
    with pytest.raises(ValidationError):
        Settings(database_url='postgresql+psycopg://u:p@localhost:6544/talentgo')


def test_empty_profile_patch_is_not_a_mutation():
    with pytest.raises(ValidationError):
        ProfilePatch(expected_version=1)
