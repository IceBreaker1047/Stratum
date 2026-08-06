import re 

def calculate_structural_integrity (text_length ):
    if text_length <=0 :
        return 0.0 
    if text_length <80 :
        return 0.7 
    if text_length <200 :
        return 0.85 
    return 1.0 


def calculate_entity_density (text ):

    if not text :
        return 0.0 

    words =text .split ()
    if not words :
        return 0.0 

    proper_nouns =len (re .findall (r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',text ))
    acronyms =len (re .findall (r'\b[A-Z]{2,}\b',text ))
    numerics =len (re .findall (r'\b\d+(?:\.\d+)?\b',text ))

    total_entities =proper_nouns +acronyms +numerics 
    density =(total_entities /len (words ))*100 

    return min (1.0 ,density /15.0 )


def compute_rag_score (chunk ):

    text_content =chunk .get ("content","")

    integrity =calculate_structural_integrity (len (text_content ))
    density =calculate_entity_density (text_content )
    rag_score =(integrity *0.4 )+(density *0.6 )

    return {
    "score":round (rag_score ,3 ),
    "integrity":round (integrity ,3 ),
    "density":round (density ,3 ),
    }


def process_chunks_validation (chunks ):

    for chunk in chunks :
        metrics =compute_rag_score (chunk )
        chunk ["rag_score"]=metrics ["score"]
        chunk ["rag_metrics"]=metrics 
    return chunks 
