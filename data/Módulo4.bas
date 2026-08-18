Attribute VB_Name = "Módulo4"
' Created by Leonardo Cervantes L.

Sub Convertir_PDF()
Attribute Convertir_PDF.VB_ProcData.VB_Invoke_Func = "s\n14"
'
' Convertir_PDF Macro
'
' Acceso directo: CTRL+s
'
   
    Sheets("3").Select
    Range("I44").Select
    ActiveSheet.ExportAsFixedFormat Type:=xlTypePDF, Filename:= _
        "RUTA ALTERADA POR SEGURIDAD\HC_Controlling.pdf", Quality:= _
        xlQualityStandard, IncludeDocProperties:=True, IgnorePrintAreas:=False, _
        OpenAfterPublish:=True
    
    Sheets("índice").Select
    Range("L12").Select
End Sub
