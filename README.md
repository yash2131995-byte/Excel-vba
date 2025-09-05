# Excel-vba
Excel to SAP connection

## SAP HANA 4.0 Example

The module `SAP_HANA_Connection.bas` demonstrates connecting to an SAP HANA database from Excel VBA.

1. Install the SAP HANA ODBC driver on your machine.
2. In the VBA editor, go to **Tools > References** and enable *Microsoft ActiveX Data Objects*.
3. Import `SAP_HANA_Connection.bas` into your VBA project.
4. Update the connection string with your server, port, user name, and password.
5. Call `GetHanaData` with a SQL statement or run `ExampleUsage` to populate a worksheet.

