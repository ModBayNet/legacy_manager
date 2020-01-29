UPDATE User
SET {
    username := .username[:12],
};

UPDATE GlobalRole
SET {
    name := .name[:12],
};

CREATE MIGRATION decrease_field_max_len TO {
    module default {
        type DB {
            required property schema_version -> int16;
        }

        type User {
            required property username -> str {
                constraint exclusive;
                constraint min_len_value(5);
                constraint max_len_value(12);
            };
            required property email -> str {
                constraint exclusive;
                constraint regexp(r'.+@.+\..+');
            };
            required property email_verified -> bool {
                default := false;
            };
            required property password -> bytes;
            required property avatar -> str;
            required property created_at -> datetime {
                default := datetime_current();
                readonly := true;
            };
            property edited_at -> datetime;

            property bio -> str;

            required link global_role -> GlobalRole;
        }

        type GlobalRole {
            required property name -> str {
                constraint exclusive;
                constraint max_len_value(12);
            };
            required property permissions -> bytes;
        }

        type GlobalBans {
            required link user -> User;
            required property reason -> str;
            required property until -> datetime;
        }
    }
};

COMMIT MIGRATION decrease_field_max_len;
