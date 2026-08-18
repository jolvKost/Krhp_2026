Attribute VB_Name = "Módulo3"
Sub Actualizar()
Attribute Actualizar.VB_ProcData.VB_Invoke_Func = " \n14"
'
' Actualizar Macro
'
ThisWorkbook.RefreshAll
ActiveWorkbook.RefreshAll
Sheets("RESULTADO").Select
ActiveWorkbook.RefreshAll



'
End Sub
