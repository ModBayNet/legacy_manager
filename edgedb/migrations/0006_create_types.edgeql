### SCHEMA MIGRATION START ###
CREATE MIGRATION create_types TO {
    module default {
        type DB {
            required property schema_version -> int16;
        }

        type User {
            required property nickname -> str {
                constraint exclusive;
                constraint min_len_value(5);
                constraint max_len_value(12);
                constraint regexp(r'[a-zA-Z\d]([a-zA-Z\d]|-(?=[a-zA-Z\d])){3,11}');
            };

            required property email -> str {
                constraint exclusive;
                constraint max_len_value(500);
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

            index on (str_lower(__subject__.nickname));
            index on (__subject__.email);
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

        # TODO: reason enum
        type GlobalBan {
            required link user -> User;

            property comment -> str {
                constraint max_len_value(500);
            };

            required property until -> datetime;
        }

        type Team {
            required property name -> str {
                constraint exclusive;
                constraint min_len_value(5);
                constraint max_len_value(12);
                constraint regexp(r'[a-zA-Z\d]([a-zA-Z\d]|-(?=[a-zA-Z\d])){3,11}');
            };

            required property avatar -> str;

            multi link members -> User;

            required property created_at -> datetime {
                default := datetime_current();
                readonly := true;
            };

            property edited_at -> datetime;

            index on (str_lower(__subject__.name));
        }

        type Comment {
            required link author -> User;
            required link article -> Article;

            link parent -> Comment;

            required property rating -> int16 {
                default := 0;
            };

            required property body -> str {
                constraint max_len_value(1000);
            };

            multi link attachments -> Attachment;

            required property deleted -> bool {
                default := false;
            };
        }

        # TODO: title, body
        type Article {
            link author -> User;
            link team -> Team;

            required property language -> str {
                constraint min_len_value(2);
                constraint max_len_value(2);
            };

            link original -> Article;

            required property rating -> int16 {
                default := 0;
            };

            required property state -> article_state_enum {
                default := <article_state_enum>"hidden";
            };
        }

        type ArticleRating {
            required property updated_at -> datetime {
                default := datetime_current();
            };
            required property positive -> bool;

            required link user -> User;
            required link article -> Article;

            index on ((__subject__.user, __subject__.article));
        }

        type CommentRating {
            required property edited_at -> datetime {
                default := datetime_current();
            };
            required property positive -> bool;

            required link user -> User;
            required link comment -> Comment;

            index on ((__subject__.user, __subject__.comment));
        }

        type Attachment {
            required property name -> str {
                constraint max_len_value(2);
            };

            required property attachment_type -> attachment_type_enum;

            required property created_at -> datetime {
                default := datetime_current();
                readonly := true;
            };
        }

        scalar type article_state_enum extending enum<"draft", "hidden", "published">;
        scalar type attachment_type_enum extending enum<"file", "image", "video">;
    }
};

COMMIT MIGRATION create_types;
### SCHEMA MIGRATION END ###
