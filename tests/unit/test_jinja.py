import jinja2
import unittest

from dbt_common.clients._jinja_blocks import BlockTag
from dbt_common.clients.jinja import (
    extract_toplevel_blocks,
    get_template,
    render_template,
    MacroFuzzParser,
    MacroType,
)
from dbt_common.exceptions import CompilationError


class TestBlockLexer(unittest.TestCase):
    def test_basic(self) -> None:
        body = '{{ config(foo="bar") }}\r\nselect * from this.that\r\n'
        block_data = "  \n\r\t{%- mytype foo %}" + body + "{%endmytype -%}"
        blocks = extract_toplevel_blocks(
            block_data, allowed_blocks={"mytype"}, collect_raw_data=False
        )
        self.assertEqual(len(blocks), 1)
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(b0.block_type_name, "mytype")
        self.assertEqual(b0.block_name, "foo")
        self.assertEqual(b0.contents, body)
        self.assertEqual(b0.full_block, block_data)

    def test_multiple(self) -> None:
        body_one = '{{ config(foo="bar") }}\r\nselect * from this.that\r\n'
        body_two = (
            "{{ config(bar=1)}}\r\nselect * from {% if foo %} thing "
            "{% else %} other_thing {% endif %}"
        )

        block_data = (
            "  {% mytype foo %}"
            + body_one
            + "{% endmytype %}"
            + "\r\n{% othertype bar %}"
            + body_two
            + "{% endothertype %}"
        )
        blocks = extract_toplevel_blocks(
            block_data, allowed_blocks={"mytype", "othertype"}, collect_raw_data=False
        )
        self.assertEqual(len(blocks), 2)

    def test_comments(self) -> None:
        body = '{{ config(foo="bar") }}\r\nselect * from this.that\r\n'
        comment = "{# my comment #}"
        block_data = "  \n\r\t{%- mytype foo %}" + body + "{%endmytype -%}"
        blocks = extract_toplevel_blocks(
            comment + block_data, allowed_blocks={"mytype"}, collect_raw_data=False
        )
        self.assertEqual(len(blocks), 1)
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(b0.block_type_name, "mytype")
        self.assertEqual(b0.block_name, "foo")
        self.assertEqual(b0.contents, body)
        self.assertEqual(b0.full_block, block_data)

    def test_evil_comments(self) -> None:
        body = '{{ config(foo="bar") }}\r\nselect * from this.that\r\n'
        comment = (
            "{# external comment {% othertype bar %} select * from "
            "thing.other_thing{% endothertype %} #}"
        )
        block_data = "  \n\r\t{%- mytype foo %}" + body + "{%endmytype -%}"
        blocks = extract_toplevel_blocks(
            comment + block_data, allowed_blocks={"mytype"}, collect_raw_data=False
        )
        self.assertEqual(len(blocks), 1)
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(b0.block_type_name, "mytype")
        self.assertEqual(b0.block_name, "foo")
        self.assertEqual(b0.contents, body)
        self.assertEqual(b0.full_block, block_data)

    def test_nested_comments(self) -> None:
        body = (
            '{# my comment #} {{ config(foo="bar") }}'
            "\r\nselect * from {# my other comment embedding {% endmytype %} #} this.that\r\n"
        )
        block_data = "  \n\r\t{%- mytype foo %}" + body + "{% endmytype -%}"
        comment = (
            "{# external comment {% othertype bar %} select * from "
            "thing.other_thing{% endothertype %} #}"
        )
        blocks = extract_toplevel_blocks(
            comment + block_data, allowed_blocks={"mytype"}, collect_raw_data=False
        )
        self.assertEqual(len(blocks), 1)
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(b0.block_type_name, "mytype")
        self.assertEqual(b0.block_name, "foo")
        self.assertEqual(b0.contents, body)
        self.assertEqual(b0.full_block, block_data)

    def test_complex_file(self) -> None:
        blocks = extract_toplevel_blocks(
            complex_snapshot_file, allowed_blocks={"mytype", "myothertype"}, collect_raw_data=False
        )
        self.assertEqual(len(blocks), 3)
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(b0.block_type_name, "mytype")
        self.assertEqual(b0.block_name, "foo")
        self.assertEqual(b0.full_block, "{% mytype foo %} some stuff {% endmytype %}")
        self.assertEqual(b0.contents, " some stuff ")

        b1 = blocks[1]
        assert isinstance(b1, BlockTag)
        self.assertEqual(b1.block_type_name, "mytype")
        self.assertEqual(b1.block_name, "bar")
        self.assertEqual(b1.full_block, bar_block)
        self.assertEqual(b1.contents, bar_block[16:-15].rstrip())

        b2 = blocks[2]
        assert isinstance(b2, BlockTag)
        self.assertEqual(b2.block_type_name, "myothertype")
        self.assertEqual(b2.block_name, "x")
        self.assertEqual(b2.full_block, x_block.strip())
        self.assertEqual(
            b2.contents,
            x_block[len("\n{% myothertype x %}") : -len("{% endmyothertype %}\n")],
        )

    def test_peaceful_macro_coexistence(self) -> None:
        body = (
            "{# my macro #} {% macro foo(a, b) %} do a thing "
            "{%- endmacro %} {# my model #} {% a b %} test {% enda %}"
        )
        blocks = extract_toplevel_blocks(
            body, allowed_blocks={"macro", "a"}, collect_raw_data=True
        )
        self.assertEqual(len(blocks), 4)
        self.assertEqual(blocks[0].full_block, "{# my macro #} ")

        b1 = blocks[1]
        assert isinstance(b1, BlockTag)
        self.assertEqual(b1.block_type_name, "macro")
        self.assertEqual(b1.block_name, "foo")
        self.assertEqual(b1.contents, " do a thing")

        self.assertEqual(blocks[2].full_block, " {# my model #} ")

        b3 = blocks[3]
        assert isinstance(b3, BlockTag)
        self.assertEqual(b3.block_type_name, "a")
        self.assertEqual(b3.block_name, "b")
        self.assertEqual(b3.contents, " test ")

    def test_macro_with_trailing_data(self) -> None:
        body = (
            "{# my macro #} {% macro foo(a, b) %} do a thing {%- endmacro %} "
            "{# my model #} {% a b %} test {% enda %} raw data so cool"
        )
        blocks = extract_toplevel_blocks(
            body, allowed_blocks={"macro", "a"}, collect_raw_data=True
        )
        self.assertEqual(len(blocks), 5)
        self.assertEqual(blocks[0].full_block, "{# my macro #} ")

        b1 = blocks[1]
        assert isinstance(b1, BlockTag)
        self.assertEqual(b1.block_type_name, "macro")
        self.assertEqual(b1.block_name, "foo")
        self.assertEqual(b1.contents, " do a thing")

        self.assertEqual(blocks[2].full_block, " {# my model #} ")

        b3 = blocks[3]
        assert isinstance(b3, BlockTag)
        self.assertEqual(b3.block_type_name, "a")
        self.assertEqual(b3.block_name, "b")
        self.assertEqual(b3.contents, " test ")

        self.assertEqual(blocks[4].full_block, " raw data so cool")

    def test_macro_with_crazy_args(self) -> None:
        body = (
            """{% macro foo(a, b=asdf("cool this is 'embedded'" * 3) + external_var, c)%}"""
            "cool{# block comment with {% endmacro %} in it #} stuff here "
            "{% endmacro %}"
        )
        blocks = extract_toplevel_blocks(body, allowed_blocks={"macro"}, collect_raw_data=False)
        self.assertEqual(len(blocks), 1)
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(b0.block_type_name, "macro")
        self.assertEqual(b0.block_name, "foo")
        self.assertEqual(
            blocks[0].contents, "cool{# block comment with {% endmacro %} in it #} stuff here "
        )

    def test_materialization_parse(self) -> None:
        body = "{% materialization xxx, default %} ... {% endmaterialization %}"
        blocks = extract_toplevel_blocks(
            body, allowed_blocks={"materialization"}, collect_raw_data=False
        )
        self.assertEqual(len(blocks), 1)
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(b0.block_type_name, "materialization")
        self.assertEqual(b0.block_name, "xxx")
        self.assertEqual(b0.full_block, body)

        body = '{% materialization xxx, adapter="other" %} ... {% endmaterialization %}'
        blocks = extract_toplevel_blocks(
            body, allowed_blocks={"materialization"}, collect_raw_data=False
        )
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(b0.block_type_name, "materialization")
        self.assertEqual(b0.block_name, "xxx")
        self.assertEqual(b0.full_block, body)

    def test_nested_not_ok(self) -> None:
        # we don't allow nesting same blocks
        body = "{% myblock a %} {% myblock b %} {% endmyblock %} {% endmyblock %}"
        with self.assertRaises(CompilationError):
            extract_toplevel_blocks(body, allowed_blocks={"myblock"})

    def test_incomplete_block_failure(self) -> None:
        fullbody = "{% myblock foo %} {% endmyblock %}"
        for length in range(len("{% myblock foo %}"), len(fullbody) - 1):
            body = fullbody[:length]
            with self.assertRaises(CompilationError):
                extract_toplevel_blocks(body, allowed_blocks={"myblock"})

    def test_wrong_end_failure(self) -> None:
        body = "{% myblock foo %} {% endotherblock %}"
        with self.assertRaises(CompilationError):
            extract_toplevel_blocks(body, allowed_blocks={"myblock", "otherblock"})

    def test_comment_no_end_failure(self) -> None:
        body = "{# "
        with self.assertRaises(CompilationError):
            extract_toplevel_blocks(body)

    def test_comment_only(self) -> None:
        body = "{# myblock #}"
        blocks = extract_toplevel_blocks(body)
        self.assertEqual(len(blocks), 1)
        blocks = extract_toplevel_blocks(body, collect_raw_data=False)
        self.assertEqual(len(blocks), 0)

    def test_comment_block_self_closing(self) -> None:
        # test the case where a comment start looks a lot like it closes itself
        # (but it doesn't in jinja!)
        body = "{#} {% myblock foo %} {#}"
        blocks = extract_toplevel_blocks(body, collect_raw_data=False)
        self.assertEqual(len(blocks), 0)

    def test_embedded_self_closing_comment_block(self) -> None:
        body = "{% myblock foo %} {#}{% endmyblock %} {#}{% endmyblock %}"
        blocks = extract_toplevel_blocks(body, allowed_blocks={"myblock"}, collect_raw_data=False)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].full_block, body)
        self.assertEqual(blocks[0].contents, " {#}{% endmyblock %} {#}")

    def test_set_statement(self) -> None:
        body = "{% set x = 1 %}{% myblock foo %}hi{% endmyblock %}"
        blocks = extract_toplevel_blocks(body, allowed_blocks={"myblock"}, collect_raw_data=False)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].full_block, "{% myblock foo %}hi{% endmyblock %}")

    def test_set_block(self) -> None:
        body = "{% set x %}1{% endset %}{% myblock foo %}hi{% endmyblock %}"
        blocks = extract_toplevel_blocks(body, allowed_blocks={"myblock"}, collect_raw_data=False)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].full_block, "{% myblock foo %}hi{% endmyblock %}")

    def test_crazy_set_statement(self) -> None:
        body = (
            '{% set x = (thing("{% myblock foo %}")) %}{% otherblock bar %}x{% endotherblock %}'
            '{% set y = otherthing("{% myblock foo %}") %}'
        )
        blocks = extract_toplevel_blocks(
            body, allowed_blocks={"otherblock"}, collect_raw_data=False
        )
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].full_block, "{% otherblock bar %}x{% endotherblock %}")
        self.assertEqual(blocks[0].block_type_name, "otherblock")

    def test_do_statement(self) -> None:
        body = "{% do thing.update() %}{% myblock foo %}hi{% endmyblock %}"
        blocks = extract_toplevel_blocks(body, allowed_blocks={"myblock"}, collect_raw_data=False)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].full_block, "{% myblock foo %}hi{% endmyblock %}")

    def test_deceptive_do_statement(self) -> None:
        body = "{% do thing %}{% myblock foo %}hi{% endmyblock %}"
        blocks = extract_toplevel_blocks(body, allowed_blocks={"myblock"}, collect_raw_data=False)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].full_block, "{% myblock foo %}hi{% endmyblock %}")

    def test_do_block(self) -> None:
        body = "{% do %}thing.update(){% enddo %}{% myblock foo %}hi{% endmyblock %}"
        blocks = extract_toplevel_blocks(
            body, allowed_blocks={"do", "myblock"}, collect_raw_data=False
        )
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].contents, "thing.update()")
        self.assertEqual(blocks[0].block_type_name, "do")
        self.assertEqual(blocks[1].full_block, "{% myblock foo %}hi{% endmyblock %}")

    def test_crazy_do_statement(self) -> None:
        body = (
            '{% do (thing("{% myblock foo %}")) %}{% otherblock bar %}x{% endotherblock %}'
            '{% do otherthing("{% myblock foo %}") %}{% myblock x %}hi{% endmyblock %}'
        )
        blocks = extract_toplevel_blocks(
            body, allowed_blocks={"myblock", "otherblock"}, collect_raw_data=False
        )
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].full_block, "{% otherblock bar %}x{% endotherblock %}")
        self.assertEqual(blocks[0].block_type_name, "otherblock")
        self.assertEqual(blocks[1].full_block, "{% myblock x %}hi{% endmyblock %}")
        self.assertEqual(blocks[1].block_type_name, "myblock")

    def test_awful_jinja(self) -> None:
        blocks = extract_toplevel_blocks(
            if_you_do_this_you_are_awful,
            allowed_blocks={"snapshot", "materialization"},
            collect_raw_data=False,
        )
        self.assertEqual(len(blocks), 2)
        self.assertEqual(len([b for b in blocks if b.block_type_name == "__dbt__data"]), 0)
        self.assertEqual(blocks[0].block_type_name, "snapshot")
        self.assertEqual(
            blocks[0].contents,
            "\n    ".join(
                [
                    """{% set x = ("{% endsnapshot %}" + (40 * '%})')) %}""",
                    "{# {% endsnapshot %} #}",
                    "{% embedded %}",
                    "    some block data right here",
                    "{% endembedded %}",
                ]
            ),
        )
        self.assertEqual(blocks[1].block_type_name, "materialization")
        self.assertEqual(blocks[1].contents, "\nhi\n")

    def test_quoted_endblock_within_block(self) -> None:
        body = '{% myblock something -%}  {% set x = ("{% endmyblock %}") %}  {% endmyblock %}'
        blocks = extract_toplevel_blocks(body, allowed_blocks={"myblock"}, collect_raw_data=False)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_type_name, "myblock")
        self.assertEqual(blocks[0].contents, '{% set x = ("{% endmyblock %}") %}  ')

    def test_docs_block(self) -> None:
        body = (
            "{% docs __my_doc__ %} asdf {# nope {% enddocs %}} #} {% enddocs %}"
            '{% docs __my_other_doc__ %} asdf "{% enddocs %}'
        )
        blocks = extract_toplevel_blocks(body, allowed_blocks={"docs"}, collect_raw_data=False)
        self.assertEqual(len(blocks), 2)
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(b0.block_type_name, "docs")
        self.assertEqual(b0.contents, " asdf {# nope {% enddocs %}} #} ")
        self.assertEqual(b0.block_name, "__my_doc__")
        b1 = blocks[1]
        assert isinstance(b1, BlockTag)
        self.assertEqual(b1.block_type_name, "docs")
        self.assertEqual(b1.contents, ' asdf "')
        self.assertEqual(b1.block_name, "__my_other_doc__")

    def test_docs_block_expr(self) -> None:
        body = '{% docs more_doc %} asdf {{ "{% enddocs %}" ~ "}}" }}{% enddocs %}'
        blocks = extract_toplevel_blocks(body, allowed_blocks={"docs"}, collect_raw_data=False)
        self.assertEqual(len(blocks), 1)
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(b0.block_type_name, "docs")
        self.assertEqual(b0.contents, ' asdf {{ "{% enddocs %}" ~ "}}" }}')
        self.assertEqual(b0.block_name, "more_doc")

    def test_unclosed_model_quotes(self) -> None:
        # test case for https://github.com/dbt-labs/dbt-core/issues/1533
        body = '{% model my_model -%} select * from "something"."something_else{% endmodel %}'
        blocks = extract_toplevel_blocks(body, allowed_blocks={"model"}, collect_raw_data=False)
        self.assertEqual(len(blocks), 1)
        b0 = blocks[0]
        assert isinstance(b0, BlockTag)
        self.assertEqual(b0.block_type_name, "model")
        self.assertEqual(b0.contents, 'select * from "something"."something_else')
        self.assertEqual(b0.block_name, "my_model")

    def test_if(self) -> None:
        # if you conditionally define your macros/models, don't
        body = "{% if true %}{% macro my_macro() %} adsf {% endmacro %}{% endif %}"
        with self.assertRaises(CompilationError):
            extract_toplevel_blocks(body)

    def test_if_innocuous(self) -> None:
        body = "{% if true %}{% something %}asdfasd{% endsomething %}{% endif %}"
        blocks = extract_toplevel_blocks(body)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].full_block, body)

    def test_for(self) -> None:
        # no for-loops over macros.
        body = "{% for x in range(10) %}{% macro my_macro() %} adsf {% endmacro %}{% endfor %}"
        with self.assertRaises(CompilationError):
            extract_toplevel_blocks(body)

    def test_for_innocuous(self) -> None:
        # no for-loops over macros.
        body = (
            "{% for x in range(10) %}{% something my_something %} adsf "
            "{% endsomething %}{% endfor %}"
        )
        blocks = extract_toplevel_blocks(body)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].full_block, body)

    def test_endif(self) -> None:
        body = "{% snapshot foo %}select * from thing{% endsnapshot%}{% endif %}"
        with self.assertRaises(CompilationError) as err:
            extract_toplevel_blocks(body)
        self.assertIn(
            (
                "Got an unexpected control flow end tag, got endif but "
                "never saw a preceeding if (@ 1:53)"
            ),
            str(err.exception),
        )

    def test_if_endfor(self) -> None:
        body = "{% if x %}...{% endfor %}{% endif %}"
        with self.assertRaises(CompilationError) as err:
            extract_toplevel_blocks(body)
        self.assertIn(
            "Got an unexpected control flow end tag, got endfor but expected endif next (@ 1:13)",
            str(err.exception),
        )

    def test_if_endfor_newlines(self) -> None:
        body = "{% if x %}\n    ...\n    {% endfor %}\n{% endif %}"
        with self.assertRaises(CompilationError) as err:
            extract_toplevel_blocks(body)
        self.assertIn(
            "Got an unexpected control flow end tag, got endfor but expected endif next (@ 3:4)",
            str(err.exception),
        )


bar_block = """{% mytype bar %}
{# a comment
    that inside it has
    {% mytype baz %}
{% endmyothertype %}
{% endmytype %}
{% endmytype %}
    {#
{% endmytype %}#}

some other stuff

{%- endmytype%}"""

x_block = """
{% myothertype x %}
before
{##}
and after
{% endmyothertype %}
"""

complex_snapshot_file = (
    """
{#some stuff {% mytype foo %} #}
{% mytype foo %} some stuff {% endmytype %}

"""
    + bar_block
    + x_block
)


if_you_do_this_you_are_awful = """
{#} here is a comment with a block inside {% block x %} asdf {% endblock %} {#}
{% do
    set('foo="bar"')
%}
{% set x = ("100" + "hello'" + '%}') %}
{% snapshot something -%}
    {% set x = ("{% endsnapshot %}" + (40 * '%})')) %}
    {# {% endsnapshot %} #}
    {% embedded %}
        some block data right here
    {% endembedded %}
{%- endsnapshot %}

{% raw %}
    {% set x = SYNTAX ERROR}
{% endraw %}


{% materialization whatever, adapter='thing' %}
hi
{% endmaterialization %}
"""


def test_if_list_filter() -> None:
    jinja_string = """
        {%- if my_var | is_list -%}
            Found a list
        {%- else -%}
            Did not find a list
        {%- endif -%}
    """
    # Check with list variable
    ctx = {"my_var": ["one", "two"]}
    template = get_template(jinja_string, ctx)
    rendered = render_template(template, ctx)
    assert "Found a list" in rendered

    # Check with non-list variable
    ctx = {"my_var": "one"}
    template = get_template(jinja_string, ctx)
    rendered = render_template(template, ctx)
    assert "Did not find a list" in rendered


def test_macro_parser_parses_simple_types() -> None:
    macro_txt = """
    {% macro test_macro(param1: str, param2: int, param3: bool, param4: float, param5: Any) %}
    {% endmacro %}
    """

    env = jinja2.Environment()
    parser = MacroFuzzParser(env, macro_txt)
    result = parser.parse()
    arg_types = result.body[1].arg_types
    assert arg_types[0] == MacroType("str")
    assert arg_types[1] == MacroType("int")
    assert arg_types[2] == MacroType("bool")
    assert arg_types[3] == MacroType("float")
    assert arg_types[4] == MacroType("Any")


def test_macro_parser_parses_complex_types() -> None:
    macro_txt = """
    {% macro test_macro(param1: List[str], param2: Dict[ int,str ], param3: Optional[List[str]], param4: Dict[str, Dict[bool, Any]]) %}
    {% endmacro %}
    """

    env = jinja2.Environment()
    parser = MacroFuzzParser(env, macro_txt)
    result = parser.parse()
    arg_types = result.body[1].arg_types
    assert arg_types[0] == MacroType("List", [MacroType("str")])
    assert arg_types[1] == MacroType("Dict", [MacroType("int"), MacroType("str")])
    assert arg_types[2] == MacroType("Optional", [MacroType("List", [MacroType("str")])])
    assert arg_types[3] == MacroType(
        "Dict", [MacroType("str"), MacroType("Dict", [MacroType("bool"), MacroType("Any")])]
    )
