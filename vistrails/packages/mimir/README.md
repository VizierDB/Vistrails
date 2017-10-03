# Vistrails Mimir Package 

Mimir package requires [Mimir](https://github.com/UBOdin/mimir/) v0.2 to load properly.

#### Install the dependencies and Mimir and start the server.

[Install sbt](http://www.scala-sbt.org/release/docs/Setup.html)

```sh
$ git clone https://github.com/UBOdin/mimir.git
$ cd mimir
$ sbt runMimirVizier
```

#### Lens Params

#####    MISSING_VALUE   
        params:  ’COL_NAME’ 	
        ex:  ‘SOME_COL’ 
 
#####    SCHEMA_MATCHING
	    params: ’COL_NAME type’	
	    ex: ‘SOME_COL int’

#####    TYPE_INFERENCE
    	param: percent that conforms
    	ex: .6

#####    KEY_REPAIR
    	params: COL_NAME
    	ex: SOME_COL

#####    COMMENT
    	params: COMMENT(EXPRESSION, ‘A Comment’)
    	ex: COMMENT(SOME_COL, ‘This value is uncertain’)
    	ex: COMMENT(SOME_COL/1000, ’We lost precision here’)
    	optional param: RESULT_COLUMNS(OUTPUT_COL_NAME[, OUTPUT_COL_NAME[, ...])
    	ex: RESULT_COLUMNS(UNCERTAIN_SOME_COL)

#####    MISSING_KEY
    	params: COL_NAME
    	ex: SOME_COL
    	optional param: MISSING_ONLY(BOOLEAN)
    	ex: MISSING_ONLY(TRUE)

#####    PICKER
    	params: PICK_FROM(COL_NAME[, COL_NAME[, ...])
    	ex: PICK_FROM(SOME_COL_1, SOME_COL_2)
    	optional param: PICK_AS(OUTPUT_COL_NAME[, OUTPUT_COL_NAME[, ...])
    	optional param: HIDE_PICK_FROM(BOOLEAN) 

#####    GEOCODE
    	params: HOUSE_NUMBER(STRNUMBER_COL)
			    STREET(STRNAME_COL)
			    CITY(CITY_COL)
			    STATE(STATE_COL)
			    GEOCODER(GEOCODER_NAME)
    	ex: HOUSE_NUMBER(STRNUMBER)
		    STREET(STRNAME)
		    CITY(CITY)
		    STATE(STATE)
		    GEOCODER(GOOGLE)






### Links

links with documentation

| Name | Link |
| ------ | ------ |
| Mimir Lens Documentation | [https://github.com/UBOdin/mimir/wiki/Lenses-and-Adaptive-Schemas] |
| Mimir Source: Github | [https://github.com/UBOdin/mimir/] [PlGh] |



