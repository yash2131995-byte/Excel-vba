Attribute VB_Name = "SAP_HANA_Connection"
Option Explicit

' Wraps value in braces and escapes closing braces for ODBC connection strings.
Private Function EscapeOdbc(ByVal value As String) As String
    EscapeOdbc = "{" & Replace(value, "}", "}}") & "}"
End Function

' Establishes a connection to SAP HANA and executes a query.
' Requires reference: Tools > References > Microsoft ActiveX Data Objects x.x Library.

' Returns an open SAP HANA connection.
Public Function OpenHanaConnection( _
    ByVal ServerNode As String, _
    ByVal UserName As String, _
    ByVal Password As String) As ADODB.Connection

    Dim conn As ADODB.Connection

    Set conn = New ADODB.Connection

    ' DSN-less connection string for SAP HANA.
    ' Use HDBODBC32 for 32-bit Office installations.
    conn.ConnectionString = _
        "Driver={HDBODBC};ServerNode=" & EscapeOdbc(ServerNode) & _
        ";UID=" & EscapeOdbc(UserName) & ";PWD=" & EscapeOdbc(Password)

    conn.Open
    Set OpenHanaConnection = conn
End Function

Public Function GetHanaData( _
    ByVal Sql As String, _
    ByVal ServerNode As String, _
    ByVal UserName As String, _
    ByVal Password As String) As ADODB.Recordset

    Dim conn As ADODB.Connection
    Dim rs As ADODB.Recordset

    Set conn = OpenHanaConnection(ServerNode, UserName, Password)
    Set rs = New ADODB.Recordset

    rs.Open Sql, conn
    Set GetHanaData = rs
End Function

' Prompts for credentials, logs in, and writes the first ten rows of a
' table to the active worksheet.
Public Sub LoginAndQuery()
    Dim server As String
    Dim user As String
    Dim password As String
    Dim rs As ADODB.Recordset

    server = InputBox("Enter HANA server (host:port):", "HANA Login")
    user = InputBox("Enter user name:", "HANA Login")
    password = InputBox("Enter password:", "HANA Login")

    Set rs = GetHanaData( _
        "SELECT TOP 10 * FROM MYSCHEMA.MYTABLE", _
        server, user, password)

    ' Output to worksheet starting at cell A1
    ActiveSheet.Range("A1").CopyFromRecordset rs

    rs.Close
    rs.ActiveConnection.Close
End Sub

