from collections import Counter 
import re 

def _normalize_text (text ):
    return re .sub (r"\s+"," ",str (text )).strip ()

def construct_semantic_tree (document_elements ):
    text_elements =[el for el in document_elements if not el .get ("is_table")and not el .get ("is_image")]
    if not text_elements :
        baseline_size =0 
    else :
        sizes =[el .get ("size",0 )for el in text_elements ]
        size_counts =Counter (sizes )
        baseline_size =size_counts .most_common (1 )[0 ][0 ]

    root ={"type":"root","children":[]}
    stack =[(0 ,root )]

    for block in document_elements :
        text =_normalize_text (block .get ("text","") )

        if block .get ("is_image")or block .get ("is_table"):
            node_type ="image"if block .get ("is_image")else "table"
            leaf ={"type":node_type }

            if node_type =="image":
                leaf ["description"]=block .get ("text","[IMAGE PENDING]")
                if "base64_image"in block :
                    leaf ["base64_image"]=block ["base64_image"]
            else :
                leaf ["html"]=block .get ("html")or block .get ("text","")
                leaf ["table_data"]=block .get ("structured_rows",[])or block .get ("table_data",[])

            stack [-1 ][1 ]["children"].append (leaf )
            continue 

        if not text :
            continue 


        size =block .get ("size",0 )
        heading_level =0 

        if baseline_size >0 and size >baseline_size :
            if size >=baseline_size +1.5 :
                heading_level =1 
            elif size >=baseline_size +0.5 :
                heading_level =2 

        if heading_level >0 :
            new_node ={
            "type":"heading",
            "level":heading_level ,
            "text":text ,
            "children":[],
            }

            while stack and stack [-1 ][0 ]>=heading_level :
                stack .pop ()

            stack [-1 ][1 ]["children"].append (new_node )
            stack .append ((heading_level ,new_node ))
            continue 


        leaf ={"type":"paragraph","text":text }
        stack [-1 ][1 ]["children"].append (leaf )

    return root 


def flatten_tree_to_chunks (node ,context_dict =None ,current_chunk =None ,chunks_list =None ,target_size =800 ,max_chars =1400 ):

    if context_dict is None :
        context_dict ={}
    if chunks_list is None :
        chunks_list =[]

    node_type =node .get ("type")

    if node_type =="heading":
        level =node .get ("level",1 )
        keys_to_delete =[k for k in context_dict .keys ()if k .startswith ("h")and int (k [1 ])>=level ]
        for k in keys_to_delete :
            del context_dict [k ]
        context_dict [f"h{level}_context"]=_normalize_text (node .get ("text","") )

    def finalize_chunk (chunk ):

        if not chunk or not chunk .get ("content","").strip ():
            return 

        ctx_list =[context_dict [f"h{i}_context"]for i in range (1 ,4 )if f"h{i}_context"in context_dict ]
        prefix =f"[{' > '.join(ctx_list)}] "if ctx_list else ""

        if not chunk ["content"].startswith ("["):
            chunk ["content"]=_normalize_text (prefix +chunk ["content"])
        else :
            chunk ["content"]=_normalize_text (chunk ["content"])

        chunks_list .append (chunk )

    if node_type =="heading":
        finalize_chunk (current_chunk )
        current_chunk ={
        "type":"heading",
        **context_dict ,
        "content":f"# {_normalize_text (node.get('text', '') )}",
        }

    elif node_type =="paragraph":
        text =node .get ("text","")
        if not current_chunk or current_chunk ["type"]!="paragraph"or len (current_chunk ["content"])>target_size :
            finalize_chunk (current_chunk )
            current_chunk ={
            "type":"paragraph",
            **context_dict ,
            "content":_normalize_text (text ),
            }
        else :
            current_chunk ["content"]=_normalize_text (current_chunk ["content"] +" "+text )

    elif node_type =="table":
        finalize_chunk (current_chunk )
        chunks_list .append ({
        "type":"table",
        **context_dict ,
        "content":_normalize_text (node .get ("html")or node .get ("text","") ),
        })
        current_chunk =None 

    elif node_type =="image":
        finalize_chunk (current_chunk )
        img_chunk ={
        "type":"image",
        **context_dict ,
        "content":_normalize_text (f"Image Description: {node.get('description', '')}"),
        }

        if "base64_image"in node :
            img_chunk ["base64_image"]=node ["base64_image"]

        chunks_list .append (img_chunk )
        current_chunk =None 

    for child in node .get ("children",[]):
        current_chunk =flatten_tree_to_chunks (child ,context_dict .copy (),current_chunk ,chunks_list ,target_size ,max_chars )

    if node_type =="root":
        finalize_chunk (current_chunk )
        return chunks_list 

    return current_chunk 