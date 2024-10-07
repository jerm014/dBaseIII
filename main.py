import cmd
import shlex
import json
import os
from collections import OrderedDict

class Field:
    def __init__(self, name, type, width, decimals=0):
        self.name = name
        self.type = type
        self.width = width
        self.decimals = decimals

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "width": self.width,
            "decimals": self.decimals
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data["type"], data["width"], data["decimals"])

class DBASETable:
    def __init__(self, name):
        self.name = name
        self.fields = OrderedDict()
        self.records = []
        self.current_record = 0

    def add_field(self, name, type, width, decimals=0):
        self.fields[name] = Field(name, type, width, decimals)

    def add_record(self, record):
        if len(record) != len(self.fields):
            raise ValueError("Record length does not match field count")
        self.records.append(record)

    def to_dict(self):
        return {
            "name": self.name,
            "fields": {name: field.to_dict() for name, field in self.fields.items()},
            "records": self.records,
            "current_record": self.current_record
        }

    @classmethod
    def from_dict(cls, data):
        table = cls(data["name"])
        table.fields = OrderedDict((name, Field.from_dict(field_data)) for name, field_data in data["fields"].items())
        table.records = data["records"]
        table.current_record = data["current_record"]
        return table

class DBASEInterpreter(cmd.Cmd):
    prompt = '. '  # dBASE III+ style prompt
    intro = "Welcome to the dBASE III+ Python Clone. Type help or ? to list commands.\n"

    def __init__(self):
        super().__init__()
        self.tables = {}
        self.current_table = None
        self.show_record_numbers = False
        self.relations = []
        self.load_database_state()

    def load_database_state(self):
        if os.path.exists("database_state.json"):
            with open("database_state.json", "r") as f:
                state = json.load(f)
            for table_data in state["tables"]:
                self.tables[table_data["name"]] = DBASETable.from_dict(table_data)
            self.relations = state["relations"]
            print("Database state loaded.")

    def save_database_state(self):
        state = {
            "tables": [table.to_dict() for table in self.tables.values()],
            "relations": self.relations
        }
        with open("database_state.json", "w") as f:
            json.dump(state, f, indent=2)
        print("Database state saved.")

    def do_create(self, arg):
        """CREATE <table_name>: Create a new table"""
        table_name = arg.strip().upper()
        if table_name in self.tables:
            print(f"Table {table_name} already exists.")
        else:
            self.tables[table_name] = DBASETable(table_name)
            print(f"Table {table_name} created.")

    def do_use(self, arg):
        """USE <table_name>: Open a database table"""
        table_name = arg.strip().upper()
        if table_name in self.tables:
            self.current_table = self.tables[table_name]
            print(f"Table {table_name} is now in use.")
        else:
            print(f"Table {table_name} does not exist. Creating it.")
            self.do_create(table_name)
            self.current_table = self.tables[table_name]

    def do_save(self, arg):
        """SAVE: Save the current database state"""
        self.save_database_state()

    def do_add_field(self, arg):
        """ADD FIELD <name> <type> <width> [<decimals>]: Add a field to the current table"""
        if not self.current_table:
            print("No table in use. Use the USE command first.")
            return
        args = shlex.split(arg)
        if len(args) < 3:
            print("Invalid ADD FIELD command. Use 'ADD FIELD <name> <type> <width> [<decimals>]'.")
            return
        name, type, width = args[:3]
        decimals = args[3] if len(args) > 3 else 0
        self.current_table.add_field(name.upper(), type.upper(), int(width), int(decimals))
        print(f"Field {name} added to table {self.current_table.name}.")

    def do_add_record(self, arg):
        """ADD RECORD <value1> <value2> ...: Add a record to the current table"""
        if not self.current_table:
            print("No table in use. Use the USE command first.")
            return
        values = shlex.split(arg)
        if len(values) != len(self.current_table.fields):
            print(f"Invalid number of values. Expected {len(self.current_table.fields)}, got {len(values)}.")
            return
        self.current_table.add_record(values)
        print("Record added.")

    def do_set(self, arg):
        """SET <option> <value>: Set various options"""
        args = shlex.split(arg)
        if len(args) < 2:
            print("Invalid SET command. Use 'SET <option> <value>'.")
            return
        option, value = args[0], " ".join(args[1:])
        if option.upper() == "RECORD":
            self.show_record_numbers = value.upper() == "ON"
            print(f"Record numbers are now {'ON' if self.show_record_numbers else 'OFF'}")
        elif option.upper() == "RELATION":
            self.set_relation(value)
        else:
            print(f"Unknown option: {option}")

    def set_relation(self, arg):
        """SET RELATION TO <field> INTO <table>"""
        args = arg.split()
        if len(args) < 4 or args[0].upper() != "TO" or args[2].upper() != "INTO":
            print("Invalid SET RELATION command. Use 'SET RELATION TO <field> INTO <table>'.")
            return
        field, table = args[1], args[3]
        if not self.current_table:
            print("No table in use. Use the USE command first.")
            return
        if table.upper() not in self.tables:
            print(f"Table {table} does not exist.")
            return
        if field.upper() not in self.current_table.fields:
            print(f"Field {field} does not exist in the current table.")
            return
        self.relations.append((self.current_table.name, field.upper(), table.upper()))
        print(f"Relation set: {self.current_table.name}.{field} -> {table}")

    def do_list(self, arg):
        """LIST [options]: List records in the current table"""
        if not self.current_table:
            print("No table in use. Use the USE command first.")
            return

        args = shlex.split(arg.upper())
        start = self.current_table.current_record
        end = len(self.current_table.records)
        fields_to_list = list(self.current_table.fields.keys())
        condition = None

        i = 0
        while i < len(args):
            if args[i] == "NEXT":
                end = start + int(args[i+1])
                i += 2
            elif args[i] == "REST":
                i += 1
            elif args[i] == "ALL":
                start = 0
                i += 1
            elif args[i] == "FIELDS":
                fields_to_list = []
                i += 1
                while i < len(args) and args[i] != "FOR":
                    fields_to_list.append(args[i])
                    i += 1
            elif args[i] == "FOR":
                condition = " ".join(args[i+1:])
                break
            elif args[i] == "STRUCTURE":
                self.list_structure()
                return
            else:
                i += 1

        # Get related fields
        related_fields = self.get_related_fields()
        fields_to_list.extend(related_fields)

        # Print header
        header = " ".join(f"{field:{self.get_field_width(field)}}" for field in fields_to_list)
        if self.show_record_numbers:
            header = "Record# " + header
        print(header)
        print("-" * len(header))

        # Print records
        for i, record in enumerate(self.current_table.records[start:end], start=start):
            if condition and not self.evaluate_condition(condition, record):
                continue
            record_str = self.format_record(record, fields_to_list)
            if self.show_record_numbers:
                record_str = f"{i+1:7} " + record_str
            print(record_str)

        self.current_table.current_record = end

    def get_related_fields(self):
        related_fields = []
        for relation in self.relations:
            if relation[0] == self.current_table.name:
                related_table = self.tables[relation[2]]
                related_fields.extend([f"{relation[2]}.{field}" for field in related_table.fields])
        return related_fields

    def get_field_width(self, field):
        if '.' in field:
            table_name, field_name = field.split('.')
            return self.tables[table_name].fields[field_name].width
        return self.current_table.fields[field].width

    def format_record(self, record, fields_to_list):
        formatted = []
        for field in fields_to_list:
            if '.' in field:
                # This is a related field
                related_table, related_field = field.split('.')
                relation = next((r for r in self.relations if r[0] == self.current_table.name and r[2] == related_table), None)
                if relation:
                    key_field, key_value = relation[1], record[list(self.current_table.fields.keys()).index(relation[1])]
                    related_record = next((r for r in self.tables[related_table].records if r[list(self.tables[related_table].fields.keys()).index(key_field)] == key_value), None)
                    if related_record:
                        value = related_record[list(self.tables[related_table].fields.keys()).index(related_field)]
                    else:
                        value = ""
                else:
                    value = ""
            else:
                value = record[list(self.current_table.fields.keys()).index(field)]
            formatted.append(f"{str(value):{self.get_field_width(field)}}")
        return " ".join(formatted)

    def list_structure(self):
        if not self.current_table:
            print("No table in use. Use the USE command first.")
            return
        print(f"Structure for database: {self.current_table.name}")
        print("Field Name   Type  Width  Dec")
        print("----------   ----  -----  ---")
        for field in self.current_table.fields.values():
            print(f"{field.name:<12} {field.type:<5} {field.width:5}  {field.decimals:3}")

    def evaluate_condition(self, condition, record):
        variables = {name: value for name, value in zip(self.current_table.fields.keys(), record)}
        try:
            return eval(condition, {"__builtins__": None}, variables)
        except:
            return False

    def do_quit(self, arg):
        """Quit the dBASE III+ clone"""
        self.save_database_state()
        print("Database state saved. Goodbye!")
        return True

    def default(self, line):
        print(f"Unknown command: {line}")

if __name__ == '__main__':
    DBASEInterpreter().cmdloop()
