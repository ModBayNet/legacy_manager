CREATE MIGRATION use_default_global_role TO {
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

            required link global_role -> GlobalRole {
                default := (
                    SELECT GlobalRole
                    FILTER .name = "Default"
                    LIMIT 1
                );
            };
        }

        type GlobalRole {
            required property name -> str {
                constraint exclusive;
                constraint max_len_value(12);
            };
            required property site_admin -> bool;

            required property can_like -> bool;
            required property can_edit -> bool;
            required property can_comment -> bool;
            required property can_publish -> bool;
            required property can_edit_comments -> bool;
        }

        type GlobalBan {
            required link user -> User;
            required property reason -> str;
            required property until -> datetime;
        }
    }
};

COMMIT MIGRATION use_default_global_role;
