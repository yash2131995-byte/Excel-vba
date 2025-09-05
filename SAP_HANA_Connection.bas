Attribute VB_Name = "SAP_HANA_Connection"
Option Explicit

' Establishes a connection to SAP HANA and executes a query.
' Replace the connection details with values for your server.
' Requires reference: Tools > References > Microsoft ActiveX Data Objects x.x Library.

Public Function GetHanaData(ByVal Sql As String) As ADODB.Recordset
    Dim conn As ADODB.Connection
    Dim rs As ADODB.Recordset
    
    Set conn = New ADODB.Connection
    Set rs = New ADODB.Recordset
    
    ' DSN-less connection string for SAP HANA.
    ' Use HDBODBC32 for 32-bit Office installations.
    conn.ConnectionString = _
        "Driver={HDBODBC};ServerNode=hana.example.com:30015;UID=MYUSER;PWD=MYPASSWORD"
    
    conn.Open
    rs.Open Sql, conn
    Set GetHanaData = rs
End Function

' Example usage: writes the first ten rows of a table to the active worksheet.
Public Sub ExampleUsage()
    Dim rs As ADODB.Recordset
    Set rs = GetHanaData("SELECT TOP 10 * FROM MYSCHEMA.MYTABLE")
    
    ' Output to worksheet starting at cell A1
    ActiveSheet.Range("A1").CopyFromRecordset rs
    
    rs.Close
    rs.ActiveConnection.Close
End Sub

