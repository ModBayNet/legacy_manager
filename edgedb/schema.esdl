module default {
    type DB {
        required property schema_version -> int16;
    }

    abstract type Authored {
        required link author -> User;
    }

    abstract type Datable {
        required property created_at -> datetime {
            default := datetime_current();
            readonly := true;
        };
    }

    abstract type Editable {
        property edited_at -> datetime;
    }

    type User extending Datable, Editable {
        required property nickname -> qualified_name;

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

    type GlobalRole extending Datable, Editable {
        required property name -> qualified_name;

        required property site_admin -> bool;

        required property can_like -> bool;
        required property can_edit -> bool;
        required property can_comment -> bool;
        required property can_publish -> bool;
        required property can_edit_comments -> bool;
    }

    # TODO: reason enum
    type GlobalBan extending Datable, Authored {
        required link user -> User;

        property comment -> str {
            constraint max_len_value(500);
        };

        required property until -> datetime;
    }

    type Team extending Datable, Editable {
        required property name -> qualified_name;
        required property avatar -> str;

        multi link members -> User;

        index on (str_lower(__subject__.name));
    }

    type Comment extending Authored, Datable, Editable {
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
    type Article extending Authored, Datable, Editable {
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

    type ArticleRating extending Authored, Editable {
        required property positive -> bool;

        required link article -> Article;

        index on ((__subject__.author, __subject__.article));
    }

    type CommentRating extending Authored, Editable {
        required property positive -> bool;

        required link comment -> Comment;

        index on ((__subject__.author, __subject__.comment));
    }

    type Attachment extending Datable {
        required property name -> str {
            constraint max_len_value(256);
        };

        required property attachment_type -> attachment_type_enum;
    }

    scalar type qualified_name extending str {
        constraint exclusive on (str_lower(__subject__));
        constraint min_len_value(5);
        constraint max_len_value(12);
        constraint regexp(r'[a-zA-Z\d]([a-zA-Z\d]|-(?=[a-zA-Z\d])){3,11}');
    }

    scalar type article_state_enum extending enum<"draft", "hidden", "published">;

    scalar type attachment_type_enum extending enum<"file", "image", "video">;
}
