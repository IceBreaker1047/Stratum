def extract_tables (page ,page_number =None ):

    tables =page .find_tables ()

    table_elements =[]



    for table in tables :

        extracted_data =table .extract ()



        if not extracted_data :

            continue 



        all_empty =all (

        not cell or str (cell ).strip ()==""

        for row in extracted_data 

        for cell in row 

        )

        if all_empty :

            continue 



        num_rows =len (extracted_data )

        num_cols =len (extracted_data [0 ])if num_rows >0 else 0 



        covered =set ()



        md_table_rows =[]



        for r in range (num_rows ):

            md_row =[]



            for c in range (num_cols ):

                if (r ,c )in covered :

                    continue 



                val =extracted_data [r ][c ]

                if val is None :

                    val =""





                w =1 

                while c +w <num_cols and extracted_data [r ][c +w ]is None and (r ,c +w )not in covered :

                    w +=1 





                h =1 

                while r +h <num_rows :

                    can_span =True 

                    for j in range (w ):

                        if (r +h ,c +j )in covered or extracted_data [r +h ][c +j ]is not None :

                            can_span =False 

                            break 

                    if can_span :

                        h +=1 

                    else :

                        break 





                for i in range (h ):

                    for j in range (w ):

                        covered .add ((r +i ,c +j ))



                text =str (val ).replace ("\n"," ").strip ()

                if text .lower ()=="none":

                    text =""



                md_row .append (text )



                tag ="th"if r ==0 else "td"





            md_table_rows .append ("| "+" | ".join (md_row )+" |")

        table_text =" ".join (row for row in md_table_rows if row .strip () )



        table_elements .append ({

        "text":table_text ,

        "size":0 ,

        "bbox":table .bbox ,

        "is_table":True ,

        "page_number":page_number ,

        "row_count":num_rows ,

        "col_count":num_cols 

        })



    return table_elements 
