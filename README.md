# Excel-vba
Excel to SAP connection

## SAP HANA 4.0 Example

The module `SAP_HANA_Connection.bas` demonstrates connecting to an SAP HANA database from Excel VBA.

1. Install the SAP HANA ODBC driver on your machine.
2. In the VBA editor, go to **Tools > References** and enable *Microsoft ActiveX Data Objects*.
3. Import `SAP_HANA_Connection.bas` into your VBA project.
4. Call `GetHanaData` with your SQL statement, server node, user name, and password (see `ExampleUsage` for a template).
5. Use the returned recordset to populate a worksheet or otherwise consume the data.

