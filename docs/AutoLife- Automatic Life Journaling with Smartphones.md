
## Page 1

# AutoLife: Automatic Life Journaling with Smartphones and LLMs

Huatao Xu¹, Panrong Tong², Mo Li¹, Mani Srivastava³
¹Hong Kong University of Science and Technology, ²Alibaba Group,
³University of California Los Angeles
Email:huatao@ust.hk, panrong@alibaba.inc, mbs@ucla.edu, lim@cse.ust.hk

## ABSTRACT

This paper introduces a novel mobile sensing application - *life journaling* - designed to generate semantic descriptions of users’ daily lives. We present AutoLife, an automatic life journaling system based on commercial smartphones. AutoLife only inputs low-cost sensor data (without photos or audio) from smartphones and can automatically generate comprehensive life journals for users. To achieve this, we first derive time, motion, and location contexts from multimodal sensor data, and harness the zero-shot capabilities of Large Language Models (LLMs), enriched with commonsense knowledge about human lives, to interpret diverse contexts and generate life journals. To manage the task complexity and long sensing duration, a multilayer framework is proposed, which decomposes tasks and seamlessly integrates LLMs with other techniques for life journaling. This study establishes a real-life dataset as a benchmark and extensive experiment results demonstrate that AutoLife produces accurate and reliable life journals.

## KEYWORDS

Mobile Sensing, Life Journaling, Large Language Model

## 1 INTRODUCTION

The widespread adoption of mobile devices like smartphones has significantly transformed many aspects of daily life. Beyond traditional mobile applications, this paper introduces a novel mobile sensing application named **"Life Journaling"** – *an approach to automatically generate detailed semantic descriptions of a person’s daily life*. Figure 1 presents an example of a journal generated from such an envisioned life journaling application, which offers natural and semantic descriptions of the person’s life context including key activities, behaviors, and circumstances in a comprehensive way. We believe life journaling is a very useful application and can support numerous downstream use cases, including personalized recommendations based on user behaviors, automatic annotation or organization of personal photos or video clips based on daily lives, optimizing daily routines for health, and many more.

Unfortunately, to the best of our knowledge, there is no existing solution for such a valuable application at present. Existing lifelogging systems [12, 28, 36] focus on recording daily life as raw digital data such as videos or sensor readings rather than understanding high-level life semantics. Prior human activity recognition (HAR) studies [29, 64, 69, 70, 76, 80] attempt to identify user activities by predicting motion labels like "walking" or "jogging", which are far less informative compared to generating rich life contexts as targeted by life journaling. While there are several commercial digital journaling apps, such as Day One [13] and Journal [30], they are not designed to automatically generate journals and rely heavily on human inputs. So, there is a significant gap in building a viable life journaling system at present.

To fill the gap, this paper presents **AutoLife**, an automatic life journaling system that generates journals of users’ daily lives based on smartphone sensor data. A key feature is that AutoLife requires no user input — all a user needs to do is to carry their own smartphone while going about their activities. As shown in Figure 1, AutoLife processes various sensor readings and other data sources (without photos or audio) accessible from the smartphone, outputting detailed journals of the user’s daily life. An essential challenge faced in developing such a system is *how to fuse those multimodal sensor*

&lt;watermark&gt;arXiv:2412.15714v2 [cs.AI] 23 Dec 2024&lt;/watermark&gt;

Mo Li is the corresponding author.

Conference’17, July 2017, Washington, DC, USA
2024. ACM ISBN 978-x-xxxx-xxxx-x/YY/MM
https://doi.org/10.1145/nnnnnnn.nnnnnnn

&lt;img&gt;
A flowchart showing the process of life journaling.
At the top, four icons represent different times of the day: 7 a.m., 9 a.m., 10 a.m., and 12 p.m.
Each icon shows a typical activity: sleeping, taking a bus, working, and eating lunch.
Below these icons, a smartphone is shown with various sensor data symbols (clock, GPS, etc.).
In the middle, a box labeled "AutoLife" connects the sensor data to the life journal.
The life journal is shown at the bottom right, with a text box that reads:
"After waking up, the user takes the bus to his company for work and then has lunch at a restaurant."
&lt;/img&gt;

**Figure 1:** Life journaling application.

---


## Page 2

Conference'17, July 2017, Washington, DC, USA

Huatao Xu, Panrong Tong, Mo Li, Mani Srivastava

**inputs and generate accurate yet open-vocabulary semantic descriptions?**

To the best of our knowledge, there is no existing dataset for this specific task, making conventional deep-learning solutions inapplicable. Extensive human life knowledge may be required to interpret diverse contexts, e.g., motion and time, and accordingly infer complex human behaviors. This paper builds on our key observation that such context interpretation and inference tasks align well with the strengths of Large Language Models (LLMs), which are trained on large-scale text corpora and possess extensive commonsense knowledge of human behaviors. However, directly using LLMs to analyze sensor data for life journaling can result in hallucinations or low-quality journals due to the high complexity of the task. To address this, our key approach is to extract rich and accurate contexts from sensors, fuse them as flexible texts, and leverage LLMs to synthesize comprehensive life journals from these contextual inputs. Two technical challenges are addressed in the design of AutoLife.

First, we must address a critical question, namely, *what information is desired to derive accurate life journals and how such information can be extracted from various data sources?* While numerous HAR studies [22, 29, 31, 69, 70] have been conducted, we notice that they typically produce only basic motion labels, such as "stationary" or "walking", due to limitations in sensor datasets and the constraints of motion sensors. Such motion contexts can provide some insights into user behaviors but are insufficient for generating a comprehensive journal. In AutoLife, we incorporate two additional contexts - time and location. Both are instrumental in understanding user behaviors, as illustrated in Figure 1. For instance, if a user remains stationary at a restaurant during mid-noon, it can be reasonably inferred that they are likely having lunch. To detect location context, we exploit GPS locations with geographic information systems (GIS), e.g., the Google Maps Platform [26]. While existing APIs do not reveal comprehensive location contexts, in AutoLife we propose to utilize large vision-language models (VLMs) like GPT-4o [48] to generate location context by interpreting map segments queried from GIS. We also incorporate WiFi SSID information and leverage lighter-weight LLMs like GPT-3.5 to further infer the user's surrounding environment (often when indoors).

Second, to further improve the quality of journals, we build special enhancements around the LLMs, including providing journal examples in the prompts and utilizing two LLM-based modules to pre-process the contexts and post-process the generated journals. Specifically, we address a key challenge of *how to assist LLMs in handling lengthy sensor data collected over long daily life periods?* Different from existing HAR applications interested in labeling short periods of activities [7] like a few seconds, life journaling typically spans a much longer duration over hours, which adds not only complexity to the task, but also difficulties to LLMs in handling the lengthy inputs. To address this challenge, we design a multi-layer framework that breaks life journaling into smaller and manageable subtasks. AutoLife first segments the sensor data into small windows and extracts both motion and location contexts from these segments with the combined use of conventional signal processing or LLM/VLMs. In the middle layer, AutoLife represents the contexts as text, which are then fused and refined before being sent for comprehension by the LLMs. In the last layer, the refined contexts with reduced lengths are consolidated, encapsulating extended-duration context, and finally fed to LLMs to generate the final journals. A duty-cycled data collection approach is applied to further reduce system overhead.

The proposed AutoLife system is prototyped and evaluated with a self-collected human life dataset that contains diverse behaviors like hiking, cycling, shopping, and working of 3 volunteers in Hong Kong. An Android app is developed to continuously collect sensor data from smartphones while users go about their daily activities. For each experiment, the volunteer manually creates reference journals, consisting of text descriptions of the volunteer's behaviors. To evaluate the qualities of journals generated by AutoLife, we compare the similarities between them with the reference journals using metrics such as BERTScore [77]. Our extensive experiments demonstrate that some LLMs like Claude 3 with our system can achieve an average BERTScore F1 higher than 0.7. In summary, this paper makes the following contributions:

(1) The paper for the first time showcases a novel mobile sensing application that can automatically generate life journals with commercial smartphones.
(2) We present the first life journaling system, AutoLife, which creatively incorporates both LLM/VLMs and conventional signal processing to fuse various sensor data and synthesize long-duration life journals.
(3) The system is prototyped and comprehensively evaluated. The dataset we establish will be made publicly available and may serve as a benchmark for future research on this topic.

The rest of this paper is organized as follows. Section 2 presents the related works. Sections 3-6 introduce the design of AutoLife. Section 7 provides implementation and evaluation results. Section 8 discusses and Section 9 concludes this paper.

## 2 RELATED WORKS

### 2.1 Life Logging

Lifelogging [12, 19, 28, 36] is a technique that digitizes human daily life, which can support many applications, including health monitoring and memory enhancement. With the rapid

---


## Page 3

AutoLife: Automatic Life Journaling with Smartphones and LLMs

Conference'17, July 2017, Washington, DC, USA

&lt;img&gt;A person wearing a SenseCam device around their neck.&lt;/img&gt;
Camera-based Solutions

&lt;img&gt;Screenshot of Day One app interface on a smartphone.&lt;/img&gt;
Day One

&lt;img&gt;Screenshot of Journal app interface on a smartphone.&lt;/img&gt;
Journal

Smartphone-based Solutions

Figure 2: Existing lifelogging solutions. Left shows a user wears SenseCam [21] while right shows two digital diary applications, i.e., Day One [13] and Journal [30].

proliferation of mobile devices, many mobile devices or applications have been developed for lifelogging. For example, Microsoft’s SenseCam [41] is a pioneering wearable camera designed to capture continuous photographic or video records of a person’s day. However, most lifelogging works aim at ‘logging’ the user’s daily life instead of generating high semantic journals. Additionally, many solutions require wearable cameras [9, 27, 76] or smart glasses [33], which are not ubiquitous and introduce extra costs.

Smartphones are widely available and there are numerous digital journaling applications on the market, as illustrated in Figure 2. However, all these apps require extensive manual input from users. A recent work, MindScape [43] proposes to generate personalized prompts with LLMs, such as "Your running routine has really taken off! How’s that influencing your day?" and records the user’s responses for journaling, which still requires user input. Unlike existing solutions, our approach generates life journals for users by leveraging data collected from ubiquitous devices like smartphones, eliminating the need for manual input.

### 2.2 Activity Recognition

Beyond lifelogging, Human activity recognition (HAR) is a critical research topic that aims at recognizing users’ daily activities like ‘answering the phone’ or ‘walking’. There are extensive HAR studies and wearable-based solutions [22, 29, 31, 37, 53, 55, 69, 70, 80] can be implemented on off-the-shelf smart devices and are more ubiquitous compared with vision-based [52, 64, 76] or wireless-based [34, 72, 78] solutions.

Despite significant progress in the field, several limitations persist: (1) Most existing methods [22, 29, 31, 32, 69, 70, 80] rely solely on motion sensors like inertial measurement units (IMUs), which are insufficient for distinguishing complex activities. For example, IMU data may only indicate that a user remains stationary for an extended period, without providing enough context to determine whether they are having a meal or attending a class. (2) No existing HAR models can generally and accurately recognize a wide range of motion types, primarily due to the lack of large-scale and comprehensive datasets. More importantly, motion labels obtained from existing HAR methods, such as ‘walking’ or ‘cycling’, do not provide the comprehensive information that life journals offer. In summary, current HAR approaches fall short of achieving the goals of life journaling.

### 2.3 Context Awareness

Location awareness refers to the ability of devices to detect their geographical positions while context awareness [38, 73] extends beyond simple geographical location, allowing devices or systems to interpret various aspects of their environment. Understanding location context is crucial for sensing user behaviors; for example, if a user remains stationary in a restaurant for an extended period, they are likely having a meal. In this paper, we explore a specific aspect of context awareness – "detecting the location context of devices" such as identifying whether a device is at a restaurant or a park. One approach might involve leveraging computer vision models to analyze photos and derive location contexts or scenes [59, 65, 79]. However, it is impractical to expect users to continuously capture photos to generate journals. Instead, this paper introduces a novel method to derive location contexts using low-cost and easily accessible sensor data from smartphones.

### 2.4 LLM-based Sensing

Large Language Models (LLMs) have achieved remarkable advancements across a wide range of tasks [11, 42, 46, 56, 61, 74]. These out-of-the-box capabilities demonstrate that LLMs contain vast amounts of world knowledge, acquired through extensive training on large-scale text datasets. Some works [10, 18, 35, 48, 50, 66, 71] extend LLMs into multimodal models, such as vision language models (VLMs) [35], to tackle various image-related tasks. Additionally, several studies introduce innovative LLM applications in diverse fields, such as Liu et al.’s work [39], which analyzes medical data for health-related tasks. Notably, researchers have proposed the concept of Penetrative AI [68], exploring the integration of LLMs with the physical world through IoT sensors. With embedded extensive commonsense knowledge, LLMs/VLMs can perform physical tasks by analyzing IoT signals, such as detecting heartbeats using digitized or figure-based ECG data [68]. Inspired by the idea of Penetrative AI, we propose a new application of LLMs/VLMs for deriving life journals from sensor data on smartphones.

---


## Page 4

Conference'17, July 2017, Washington, DC, USA

Huatao Xu, Panrong Tong, Mo Li, Mani Srivastava

&lt;img&gt;
A flowchart titled "Figure 3: AutoLife overview."

The flowchart shows a smartphone with various sensors (accelerometer, gyroscope, GPS, WiFi, etc.) connected to two main processes.

**Left Side:**
- **Sensors**: A box containing icons for accelerometer, gyroscope, GPS, WiFi, and other sensors.
- **Motion Context Detection**: A box with a clock icon.
- **Location Context Detection**: A box with a clock icon.
- **Context Logs**: A box listing types of context logs:
    - Time context, e.g., 11:15 a.m.
    - Motion context, e.g., stationary
    - Location context 1, e.g., restaurant
    - Location context 2, e.g., urban area

**Right Side:**
- **GIS**: A box with a map icon.
- **Life Journal**: A box with a speech bubble icon, containing the text "The user starts having lunch at a restaurant..."
- **Journal Generation**: A box with a brain icon.
- **Context Fusion & Refinement**: A box with a brain icon, leading to a dashed rectangle labeled "Refined Context Logs" which contains multiple instances of the same context log format as listed under "Context Logs".

The arrows indicate the flow of data from the sensors through the detection processes, to the context logs, and finally to the journal generation process.
&lt;/img&gt;

## 3 AUTOLIFE

### 3.1 Problem Definition

In this paper, we introduce a new application called **life journaling**, which generates journals for users’ daily lives through mobile devices. We assume that our system functions as a mobile application on these devices, with regular access to sensor data. The system takes low-cost and long-term sensor data as input, such as accelerometer readings or GPS locations. The output is a series of sentences that accurately describe the user’s daily activities, e.g., visiting a museum or resting at home.

### 3.2 Overview

Figure 3 presents the overview of AutoLife. Instead of directly feeding long-duration sensor data to LLMs for life journaling, that may cause hallucinations and low-quality journals, AutoLife optimizes the use of LLMs with various sensor data by a multi-layer framework that decomposes the life journaling task process into manageable subtasks, each addressed by specialized modules. First, AutoLife periodically accesses sensor data from smartphones in short periods. The *motion context detection* and *location context detection*, are designed to derive the user’s contexts from multiple sensor resources. Particularly, *location context detection* presents a novel approach to obtain accurate and general location contexts using LLMs or VLMs. Next, AutoLife represents these contexts as flexible texts and utilizes another LLM-based module to enhance their precision and reduce text length. Finally, AutoLife aggregates the enhanced context logs over a long duration and processes them through the *journal generation* module, where LLMs synthesize the information to generate comprehensive life journals for users.

### 3.3 Input Sensors

It is intuitive that any single sensor data, e.g., the accelerometer or GPS location, cannot provide sufficient information to infer accurate journals. Therefore, our system integrates data from multiple sensors. Below is an overview of the chosen sensor features and how they are pre-processed.

*   **Accelerometer** sensors capture the device’s accelerations. We use step-count algorithms [16] to estimate the user’s steps from a duration of accelerometer readings, which serves as another important indicator.
*   **Gyroscope** measures the device’s angular velocity, which can be integrated with the accelerometer to estimate device orientation. The human-caused acceleration [15] is also an important feature, which can be computed by fusing the two sensors.
*   **Barometer** measures air pressure, which can be used to estimate rough altitude using the barometric formula [2]. We then compute the altitude change over a time period as $\Delta h = h_i - h_j$, where $h_i$ represents the altitude at time $i$. The altitude change is a valuable feature for detecting user movement.
*   **GPS speed** reflects the user’s movement on the horizontal plane. Since satellite signals may be blocked when the user is indoors, the speed reported by the localization module can be unreliable. We filter GPS speed data when the number of detected satellites is fewer than 5.
*   **GPS location** provides the geographic coordinates, consisting of latitude and longitude. Similarly, GPS data can be unreliable indoors and we filter out locations where the horizontal accuracy radius, as reported by the Android API [4], exceeds 50 meters.
*   **WiFi** signals can also help determine the user’s location and are used for localization in the Google Fused Location Provider [3]. Recent studies [44, 68] have shown that WiFi Service Set Identifiers (SSIDs) can offer valuable insights into a user’s surroundings.

Note that during implementation, we access the geographic location from Android Fused Location Provider API [3], which fuses multiple sources including GPS and WiFi for more accurate localization.

## 4 CONTEXT DETECTION

This section will elaborate on how we fuse the input sensors and derive motion or location contexts for life journaling.

### 4.1 Motion Context

Motion information like walking is a key indicator for determining users’ behaviors. Extensive research in HAR [22, 29, 31, 32, 40, 68–70, 80] has demonstrated the potential of leveraging motion sensors to identify activities like jogging or cycling. However, these approaches cannot be directly applied to life journaling because most available public datasets

---


## Page 5

AutoLife: Automatic Life Journaling with Smartphones and LLMs
Conference’17, July 2017, Washington, DC, USA

**Algorithm 1:** Motion detection algorithm in Auto-Life.

**Input:** step count s per minute, acceleration excluding gravity a m/s², altitude change Δh m, horizontal speed v m/s.
**Output:** motion list L.

```
1 L ← [];
2 if s <= 2 & a <= 0.1 & |Δh|<= 0.1 & v <= 0.1 then
3    L ← L + ['stationary'];
4 else if s <= 10 & |Δh|<= 1.0 & v < 0.5 then
5    L ← L + ['limited motion'];
6 end
7 if s >= 140 & 2.0 <= v <= 5.0 then
8    L ← L + ['jogging/running'];
9 if s >= 50 & v < 1.8 then
10   L ← L + ['walking'];
11 if s >= 50 & v >= 4.0 then
12   L ← L + ['cycling'];
13 if (s <= 5 & v > 2) | v > 5 then
14   L ← L + ['vehicle/subway/ferry/train'];
15 if s <= 10 & Δh > 2.5 & v < 2 then
16   L ← L + ['escalator/elevator'];
17 end
18 return L;
```

[40, 57, 58, 75] cover only a limited range of sensor modalities, users, devices, and labeled data, making it challenging to build general models for recognizing activities.

To build a general solution, we propose a new rule-based motion detection algorithm by exploiting multimodal sensors. As outlined in Algorithm 1, our approach fuses multiple features post-process by raw sensor data, including step counts, acceleration excluding gravity, altitude change, and GPS horizontal speed. The rules are based on commonsense knowledge; for example, if the step count is low while the speed is high, the user is likely using transportation. Despite leveraging multiple sources, ambiguities still arise when determining certain activities, so our algorithm acknowledges the limitations of sensors and can output multiple possible motions when the input data is inconclusive, e.g., ‘escalator/elevator’. Later, we leverage LLMs to reduce these ambiguities by incorporating location context.

We reference thresholds in gait and activity analysis studies [8, 62, 63] and fine-tune them using our dataset. We evaluate the proposed algorithm on our dataset (detailed in Section 7.1) and Sussex-Huawei Locomotion Dataset [20], where certain labels like ‘car’ and ‘bus’ are merged. The algorithm is tested on 831 samples from our dataset and 13,544 samples from the Sussex-Huawei dataset. The results show that the algorithm achieves an average precision of 0.864 and 0.773 on the two datasets, respectively. Further evaluation experiments demonstrate that the motions recognized by our algorithm can enhance the quality of life journals.

### 4.2 Location Context

Location context is also crucial for accurately inferring a user’s activity. However, detecting location contexts using ubiquitous sensors on smartphones is not straightforward. In this section, we design a low-cost solution for detecting location contexts.

#### 4.2.1 Location Context from GPS location

Modern smartphones can easily access geographic locations, including latitude and longitude, through their positioning modules. However, GPS locations often do not provide sufficient information on their own. Our first idea is to exploit these locations with the existing Geographic Information Systems (GIS) like Google Maps [26] or OpenStreetMap [49], which offer comprehensive details about places worldwide and are widely used in daily life. However, identifying the location contexts from existing GIS is non-trivial. We first explore two available APIs of these GIS platforms:

*   **Reverse Geocoding API** [25, 45]: This API converts geographic coordinates into addresses, providing a basic level of location context, such as ‘South Ferry, New York, NY 10004’.
*   **Places API** [24]: This API generates a list of nearby places within a specified radius around a geographic coordinate. It is important to note that there is a maximum limit on the number of place results, such as 20 for the Google Maps Places API [24].

We illustrate three example results of the above methods in Figure 4, which cover different scenarios, including public, residential, and recreational areas. The addresses obtained from the Reverse Geocoding API do not convey informative location context. While the Places API can provide extensive landmarks information in urban areas like the ‘New York Stock Exchange’ and ‘Charging Bull’, it has limitations. In residential areas, as shown in the second example, the Places API tends to be biased toward public places, such as sports or educational centers, and may not accurately reflect the residential context. Furthermore, when the device is in a suburban area, both APIs may fail to return any relevant context. In summary, these two methods are not universally effective for location context detection across all scenarios.

To address this challenge, we observe that map segments on the other hand can provide more general and stable information than address or place texts. A map itself is an image where shapes, colors, and patterns all convey significant contextual information. For instance, the grey rectangles in the second case of Figure 4 likely represent houses, while the blue area in the third case indicates a body of water. More

---


## Page 6

Conference’17, July 2017, Washington, DC, USA

Huatao Xu, Panrong Tong, Mo Li, Mani Srivastava

&lt;img&gt;Map showing location (40.703243,-74.014222) with reverse geocoding API result: 'Reverse geocoding API: 61 State St, New York, NY 10004, USA' and places API result: 'Places API: 'The Battery', 'Charging Bull', 'Whitehall Terminal', 'Statue City Cruises Battery Park', 'New York Stock Exchange', 'South Ferry', ...'&lt;/img&gt;
&lt;img&gt;Map showing location (40.737569,-74.410467) with reverse geocoding API result: 'Reverse geocoding API: 64 Dale Dr, Chatham Township, NJ 07928, USA' and places API result: 'Places API: 'St Vincent Martyr Cemetery', 'Precision Spine and Sport', 'Dr. David Dijkstra', 'Chatham Counseling & Educational Center', ...'&lt;/img&gt;
&lt;img&gt;Map showing location (36.844327,-88.119028) with reverse geocoding API result: 'Reverse geocoding API: RVVJ+P9 Fenton, KY, USA' and places API result: 'Places API: ...'&lt;/img&gt;

Figure 4: Examples of detecting location contexts with address and places. Results are from Google Maps Geocoding and Places API, respectively. The left side shows the map segments centered at corresponding locations.

&lt;img&gt;Diagram showing a map image connected to a VLM, which then provides a prompt to the LLM.&lt;/img&gt;
**Prompt**
You are a helpful assistant that can analyze the uploaded map. Identify key features with the following categories: transportation infrastructure, natural features, built environment, and additional landmarks. Then provide a brief summary of the map's central region.

**Summary of Response**

The central region of the map is a culturally and commercially vibrant area. It features the National Museum of the American Indian, which is a significant cultural and educational institution. The area is well-equipped with infrastructure including main roads like State St, Bridge St, and Pearl St, as well as multiple bus stops indicating good public transit accessibility. The Battery park offers a large green space with waterfront views, providing a natural retreat within the urban setting. Commercial establishments such as a Starbucks and coworking offices in One State Street Plaza highlight the area's business activity. This map likely represents a well-developed urban area with a blend of cultural, commercial, and natural features.

**Summary of Response**

**2** The central region of the map is characterized by Dale Dr, which runs horizontally through the middle. This street is flanked by multiple buildings, likely homes, indicating a residential neighborhood with a grid-like street plan. There are no notable natural features or landmarks present in this segment of the map, emphasizing its residential nature.

**3** The central region of the map is predominantly covered in green, indicating a natural area, such as a forest or park. A notable feature is the lake in the lower left corner. There are no visible signs of transportation infrastructure or built environment, suggesting this map segment represents a largely natural or undeveloped region.

**Figure 5: Examples of detecting location contexts by analyzing map images with VLM. The results are generated from GPT-4o [48] and input images are the maps in Figure 4.**

importantly, map segments are widely available and can be easily accessed through services like the Google Maps Static API [23]. Therefore, we propose analyzing map images to derive more comprehensive location contexts.

However, interpreting maps is challenging, as it requires extensive knowledge to understand the shapes, colors, and texts presented in the images. Inspired by the rapid progress and success of recent vision language models (VLMs) [10, 18, 35, 48, 66], we propose leveraging existing VLMs to analyze map images without any additional training. As shown in Figure 5, we use GPT-4o [48] to detect location contexts from the three maps in Figure 4. The results demonstrate GPT-4o’s strong zero-shot ability to extract key features from the maps and generate accurate contexts for all three cases. Thus, modern VLMs offer a new and reliable approach to identifying location contexts from maps.

We use the Google Static Map API [23] to retrieve map images, configuring three key parameters: the central location of the map (specified by geographic coordinates from the positioning module), the image size (500×500 pixels), and the zoom level (18), which ensures the map covers a sufficient area encompassing approximately 250×250 m² [23]. To avoid redundant API calls for maps with close centers, we implement a grid system with a size of 100×100 m² and all co-ordinates in the same grid share the map image and location contexts. Additionally, since map information is generally stable, we maintain a key-value database to store the location contexts generated by VLMs. The key is a string representing the grid location, while the value is a string containing the location context. This approach allows us to reuse the inference results from VLMs, further reducing costs.

**Objective:** Determine users' location context by WiFi data from their smartphone.
**Background:** ... Scanned APs indicate user's proximity to them, and their SSIDs can hint at specific locations.
**Task:** Now infer a user's surrounding conditions with the following SSID list: ["eduroam", "Alumni", ....]
**Response Format:**
**Reasoning:** Provide a comprehensive analysis of the SSIDs.
**Summary:** Conclude with a brief summary of your findings.

&lt;img&gt;Diagram showing a Prompt being fed into a LLM, which outputs "The user is most likely in a university campus."&lt;/img&gt;

**Figure 6: Location context detection with WiFi SSID. The red underlined texts in the prompt would be replaced by the scanned WiFi SSIDs.**

**4.2.2 Location Context from WiFi SSID.** In addition to GPS locations, WiFi Service Set Identifiers (SSIDs) can also provide valuable location context [44, 68]. For example, if a

---


## Page 7

AutoLife: Automatic Life Journaling with Smartphones and LLMs
Conference'17, July 2017, Washington, DC, USA

&lt;img&gt;A pie chart showing the performance of GPT-4o on location context detection with maps. The chart has four segments: 68.6% (green), 27.9% (blue), 3.5% (light blue), and 2% (gray).&lt;/img&gt;
GPT-4o
Average: 3.65

&lt;img&gt;A pie chart showing the performance of Gemini 1.5 Flash on location context detection with maps. The chart has four segments: 50.5% (green), 46.5% (blue), 3.0% (light blue), and 2% (gray).&lt;/img&gt;
Gemini 1.5 Flash
Average: 3.47

&lt;img&gt;A pie chart showing the performance of Claude 3 Sonnet on location context detection with maps. The chart has four segments: 62.4% (green), 32.9% (blue), 4.7% (light blue), and 2% (gray).&lt;/img&gt;
Claude 3.5 Sonnet
Average: 3.58

Figure 7: Performance of VLMs on location context detection with maps. The higher the scores, the better the performance.

smartphone detects an SSID containing ‘Starbucks’, it suggests that the user is near or inside a Starbucks. However, analyzing SSIDs requires a substantial amount of common-sense knowledge to interpret the names of various places, including restaurants, transportation hubs, landmarks, and more. To address this, we adapt the approach from [68] and utilize LLMs, such as ChatGPT [46], to derive location contexts from WiFi SSIDs as shown in Figure 6. We observe that many WiFi access points in public networks share identical SSIDs, such as ‘eduroam’. To optimize token usage, we preprocess the SSID list by removing duplicate SSIDs.

### 4.3 Location Context Evaluation

We conduct two experiments to evaluate the performance of existing commercial LLMs/VLMs in location context detection. The data collection process is detailed in Section 6. We find these tasks are special as analyzing maps or WiFi SSIDs requires a broad base of general knowledge, an area where existing LLMs may often outperform humans [47]. To assess their performance, we evaluate the models by judging or rating their responses. We recruited 18 volunteers and collected a total of 330 and 360 scores for the two tasks, respectively.

In the first task of map interpretation using VLMs, we evaluate the performance of GPT-4o (gpt-4o-2024-05-13) [48], Gemini Flash (gemini-1.5-flash) [60], and Claude 3 Sonnet (claude-3-5-sonnet-20240620) [6]. We instruct the VLMs to generate descriptions for maps and designed a questionnaire to rate these descriptions. Each question included one map image, a description generated by an LLM, and four rating options ranging from 1 to 4, where ‘1’ indicates "The description mismatches the map" and ‘4’ represents "The description well matches the map". The questions were randomly sampled from 300 instances of map segments in Hong Kong, and the models were anonymized to the volunteers.

Figure 7 presents the overall scores of the three VLMs that demonstrate impressive performance in this task, which requires interpreting shapes and texts (both in English and Chinese). The average scores were high, with GPT-4o, Gemini Flash, and Claude 3 Sonnet achieving 3.68, 3.47, and 3.58, respectively. Notably, none of the models hallucinates and receives a score of 1, underscoring the feasibility of using VLMs to interpret maps for location context detection.

The second task, location context detection using WiFi SSIDs, is considerably more challenging for humans, as SSIDs often contain diverse and unfamiliar text, such as restaurant, company, or place names. We conducted 50 tests where volunteers rated the performance of LLMs on a scale from 1 to 4, with the assistance of ground-truth location context. For the remaining 310 tests, we had the LLMs compete against each other, asking volunteers to select the best response among. We also introduced two additional options: "SSIDs are not informative"—when SSIDs lack unique identifiers for detailed location contexts, and "Not sure"—when the models gives similar responses or when the SSIDs were particularly difficult to analyze. Since this task involves only processing text inputs, we replaced GPT-4o (gpt-4o-2024-05-13) with lighter-weight GPT-3.5 (gpt-3.5-turbo-0125).

Table 1 presents the performance of the three models across 360 tests. In this task, recall refers to the ratio of instances where the LLMs successfully generate valid context relative to the instances where volunteers consider SSIDs to be informative. Specificity represents the ratio of instances where LLMs generate valid context relative to the instances where volunteers believe SSIDs lack location indicators. Win rates indicate the number of cases in which each model beats the other two. Overall, all models achieve good performance, demonstrating that using them to analyze SSIDs for location context detection is effective.

<table>
<thead>
<tr>
<th>Metric</th>
<th>GPT-3.5</th>
<th>Gemini 1.5 Flash</th>
<th>Claude 3 Sonnet</th>
</tr>
</thead>
<tbody>
<tr>
<td>Score (↑)</td>
<td>3.51</td>
<td>3.43</td>
<td>3.25</td>
</tr>
<tr>
<td>Win Rate (↑)</td>
<td>42.2%</td>
<td>31.8%</td>
<td>26.0%</td>
</tr>
<tr>
<td>Recall (↑)</td>
<td>0.928</td>
<td>0.962</td>
<td><strong>0.997</strong></td>
</tr>
<tr>
<td>Specificity (↑)</td>
<td><strong>0.895</strong></td>
<td>0.842</td>
<td>0.789</td>
</tr>
</tbody>
</table>

## 5 CONTEXT FUSION

Now we have explored how to detect users’ contexts with various sensors and this section will elaborate on how these contexts can be fused to enhance precision.

### 5.1 Location Context Fusion

Both map-based and SSID-based methods can provide valuable location contexts; however, we observe they have distinct features:

*   **Map-based location context** is effective in almost all situations but tends to provide only general descriptions, such as identifying an area as commercial or

---


## Page 8

Conference'17, July 2017, Washington, DC, USA
Huatao Xu, Panrong Tong, Mo Li, Mani Srivastava

&lt;img&gt;Wi-Fi icon with connection strength bars.&lt;/img&gt;
**WiFi**

&lt;img&gt;Satellite dish icon.&lt;/img&gt;
**Satellite**

&lt;img&gt;Barometer icon.&lt;/img&gt;
**Barometer**

&lt;img&gt;IMU (Inertial Measurement Unit) icon.&lt;/img&gt;
**IMU**

Selection → ["Wi-Fi.HK", "Smile", "Hoohoohoo", ...]
Positioning Module → GIS → SSID list coordinate Map Image
Altitude Calculator → speed altitude change
Orientation Estimation → acceleration
Step Counter → step count
Rule-based Motion Detection

GIS
SSID list
coordinate
Map Image

LLM → Hong Kong...
VLM → Hiram's Highway ...

Fuse location contexts and keep the most detailed context.
Prompt
Select most probable motion with location context.
Prompt
Possible motions: being in a vehicle, subway, ferry, or train.
Possible motions: being in a vehicle
Calibrated Motion
Fused Location Context

LLM → Hiram's Highway ...
LLM → Hiram's Highway ...

&lt;img&gt;Brain icon representing LLM.&lt;/img&gt;

Figure 8: **Location and motion context fusion in AutoLife.**

residential. Additionally, it struggles to offer detailed information in public areas with numerous points of interest (POIs); for example, it may not determine which specific store a user is in within a shopping mall.

- **SSID-based location context** can be fine-grained in some cases, such as identifying specific restaurants or campuses. However, it becomes less effective in suburban areas with few WiFi access points or when scanned SSIDs are not informative, such as ‘Redmi 9A’ or ‘SjFaHJ6echEs,’ which lack identifiers that can be used to derive meaningful location contexts.

Therefore, we propose fusing the two location contexts to obtain the most fine-grained context. Since both contexts are represented as text and the fusion task requires extensive commonsense knowledge, we believe LLMs are well-suited for this task. The upper part of Figure 8 illustrates the workflow for location context detection. The LLM is prompted to merge the location contexts and retain the most detailed and specific information—in the shown case, "Hiram’s Highway", as nearby SSIDs are not highly informative. If the user is in an urban area, the SSID-derived context can provide valuable information, such as identifying a restaurant by an SSID like "McDonald’s". This approach allows us to generate the most detailed and fine-grained location contexts based on multiple smartphone sensor signals.

**5.2 Motion Calibration**

With the location context, actually we can further improve the accuracy of motion contexts, especially when our rule-based method provides multiple possible options. For instance, if a user is detected at a high GPS speed, determining the exact transportation mode can be challenging. But if we know the user is on a water surface, it’s likely they are on a ferry. To achieve this, we propose calibrating the detected motion types using location context.

This task also requires a significant amount of commonsense knowledge, making LLMs an effective solution. We represent both the location and motion contexts as text and use LLMs to calibrate the motions, as illustrated in Figure 8. The LLM is prompted to "select the most probable motion given the location context". For example, if the primary location context is "Hiram’s Highway", the transportation mode is likely to be "being in a vehicle". This approach allows us to further remove the ambiguity of motions and enhance the precision of motion contexts.

**6 LIFE JOURNALING**

The previous section details how to obtain accurate contexts from sensor data, though this process is limited to short time windows, e.g., 15 seconds. But generating a life journal requires processing sensor data over much longer durations like hours. This section explains how to aggregate contexts from extended time windows and generate life journals.

**6.1 Context Refinement**

To get long-term context information, we should aggregate context logs over time. However, simply combining these contexts as texts can result in overly lengthy and less accurate data. To address this, we apply several optimizations to the context fusion process.

First, we observe that location contexts from neighboring time windows may vary in quality or detail. For example, one context might describe "a restaurant", while the context from the neighboring window can specify "a McDonald’s restaurant", with the latter providing more information. Therefore, we also need to fuse location contexts over time. Additionally, as shown in Figure 5, the location contexts generated

---


## Page 9

AutoLife: Automatic Life Journaling with Smartphones and LLMs

Conference'17, July 2017, Washington, DC, USA

&lt;img&gt;Figure 9: Journal generation in AutoLife.&lt;/img&gt;

such as, "In the morning, the user spends time at a local library, likely reading and researching".

We also observed that many LLMs, like ChatGPT, tend to include "subjective comments" on the response, such as, "The routine consists of a blend of work and leisure". To address this, we use another LLM session with the prompt - "remove any subjective comments if they exist" to further polish the journal. This process yields the final journal for the user, summarizing their behaviors over a long duration.

**6.3 Data Collection Duty Cycle**

Although life journaling requires long durations of sensor data, it is unnecessary for our system to continuously and consistently collect data from smartphones, such as scanning WiFi signals for hours, as this would consume excessive energy [17]. Therefore, we design a duty cycle for the data collection, as shown at the top of Figure 9. The system periodically activates the collection process and then enters an idle state for a while. The context detection module then processes the collected sensor data to generate contexts. The parameters $t$ and $T$ represent the collection duration and period, respectively. To allow sufficient time for the smartphone to scan WiFi and compute a more accurate step count, we set $t$ to 15 seconds. The collection period $T$ is set to 60 seconds and its impact will be evaluated in Section 7.4.

**7 EVALUATION**

**7.1 Implementation**

**APP design.** Since life journaling is a novel application, to the best of our knowledge, there is no existing dataset available for it. Therefore, we develop an Android application that runs a foreground service to regularly access sensor data, such as satellite and WiFi signals, from the system APIs. The data collection process follows the duty cycle described in Section 6.3, with all sensor data being implicitly saved in files for offline processing.

**Dataset.** We recruit 4 volunteers from Hong Kong to collect an extensive dataset in various scenarios with three smartphones including Samsung Galaxy S8, Samsung Galaxy S22, and Google Pixel 7. During the data collection process, each volunteer carries the experimental smartphone and goes about their daily activities as usual, activating the data collection in the application. The smartphone was not required to be tightly attached to the volunteers; for example, they were free to place the phone on a table while having a meal. We collect data from 58 experiments, totaling 4,417 minutes, with an average experiment duration of 76.2 minutes – significantly longer than the sensing durations, e.g., typically a few seconds, used in HAR studies. For each experiment, the corresponding volunteer provides two similar

---


## Page 10

Conference’17, July 2017, Washington, DC, USA

Huatao Xu, Panrong Tong, Mo Li, Mani Srivastava

<table>
  <tr>
    <td><strong>Scenarios</strong></td>
    <td>&lt;img&gt;A beach scene with people swimming and sunbathing under umbrellas.&lt;/img&gt; &lt;img&gt;A mountainous landscape with a body of water in the background.&lt;/img&gt;</td>
    <td>&lt;img&gt;A presentation screen showing "CPS-IoT Week" and a cityscape.&lt;/img&gt; &lt;img&gt;A conference room with attendees and a presenter.&lt;/img&gt;</td>
  </tr>
  <tr>
    <td><strong>Reference Journal</strong></td>
    <td>In the afternoon, the user visits Hap Mun Bay Beach, engaging in beach activities, then hikes the natural trails to Black Peak around Kiu Tsui Country Park.</td>
    <td>In the early afternoon, the user attends the IoT-related event, CPS-IoT Week, at the Hong Kong Science and Technology Parks (HKSTP).</td>
  </tr>
  <tr>
    <td><strong>Generated Journal</strong></td>
    <td>In the early afternoon, the user enjoys a relaxing time at Hap Mun Bay Beach, likely engaging in swimming and supervising family activities. Following this, they transition to Black Peak for outdoor exploration, participating in hiking activities amidst natural landscapes and trails.</td>
    <td>In the early afternoon, the user is engaged at a technology-focused conference or event at the Hong Kong Science Park, participating in activities related to IoT and audiovisual technology. The user spends considerable time in a stationary or limited motion state, reflecting active participation in sessions, workshops, or presentations...</td>
  </tr>
  <tr>
    <td><strong>Similarity Metric</strong></td>
    <td>chrF: (0.337), BERTScore: (Precision 0.737, Recall 0.783, F1 0.759)</td>
    <td>chrF: (0.483), BERTScore: (Precision 0.553, Recall 0.719, F1 0.625)</td>
  </tr>
</table>

**Figure 10:** Life journal examples generated by AutoLife with GPT-4o mini.

and concise text descriptions of their behaviors, referred to as the *reference journals*, for evaluation purposes.

**Models.** AutoLife has many LLM-based modules, and there are numerous potential combinations of available models. We establish a default configuration with several representative LLMs. In the location context module, we select GPT-4o (gpt-4o-2024-05-13) [48] for map interpretation and GPT-3.5 (gpt-3.5-turbo-0125) [46] for SSID interpretation. In the context fusion and journal generation modules, we adopt GPT-4o mini (gpt-4o-mini-2024-07-18).

**Prompts.** All prompts include a specified response format ("reasoning" and "summary" [67]) to constrain LLMs, and every response undergoes a keyword detection process to extract the key "summary" content, such as location context or journal entries. Due to space constraints, we illustrate key parts of the prompts in Figure 5, 8, and 9.

**Metrics.** To evaluate the quality of journals generated by AutoLife, we measure the similarities between them and the reference journals using chrF [51] and BERTScore [77], both of which are widely adopted metrics in the natural language processing domain. We also define LLMs as hallucinating if they do not follow the specified response format and the target context cannot be extracted from their responses.

**Baseline.** To comprehensively evaluate AutoLife, we also establish a baseline solution, referred to as *SenLLM* in this paper, which simply aggregates raw sensor across time and inputs them into LLMs for journal generation.

**Table 2:** Performance of AutoLife and baseline methods. ‘Hall.’ denotes hallucination while ‘P’, ‘R’, and ‘F1’ represents precision, recall, and F1 score, respectively.

<table>
  <thead>
    <tr>
      <th rowspan="2">LLM</th>
      <th rowspan="2">Method</th>
      <th rowspan="2">Hall.<br>rate (↓)</th>
      <th colspan="1">chrF (↑)</th>
      <th colspan="3">BERTScore (↑)</th>
    </tr>
    <tr>
      <th></th>
      <th>P</th>
      <th>R</th>
      <th>F1</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="2">GPT-4o</td>
      <td>SenLLM</td>
      <td>0.000</td>
      <td>0.451</td>
      <td>0.592</td>
      <td>0.680</td>
      <td>0.630</td>
    </tr>
    <tr>
      <td>AutoLife</td>
      <td>0.000</td>
      <td>0.509</td>
      <td>0.613</td>
      <td>0.772</td>
      <td>0.681</td>
    </tr>
    <tr>
      <td rowspan="2">GPT-4o<br>mini</td>
      <td>SenLLM</td>
      <td>0.000</td>
      <td>0.394</td>
      <td>0.563</td>
      <td>0.621</td>
      <td>0.588</td>
    </tr>
    <tr>
      <td>AutoLife</td>
      <td>0.000</td>
      <td><strong>0.553</strong></td>
      <td>0.641</td>
      <td>0.776</td>
      <td>0.699</td>
    </tr>
    <tr>
      <td rowspan="2">Claude<br>3 Opus</td>
      <td>SenLLM</td>
      <td>0.000</td>
      <td>0.437</td>
      <td>0.622</td>
      <td>0.692</td>
      <td>0.652</td>
    </tr>
    <tr>
      <td>AutoLife</td>
      <td>0.000</td>
      <td>0.536</td>
      <td>0.646</td>
      <td><strong>0.782</strong></td>
      <td><strong>0.704</strong></td>
    </tr>
    <tr>
      <td rowspan="2">Gemini<br>1.5 Pro</td>
      <td>SenLLM</td>
      <td>0.000</td>
      <td>0.400</td>
      <td>0.587</td>
      <td>0.645</td>
      <td>0.611</td>
    </tr>
    <tr>
      <td>AutoLife</td>
      <td>0.000</td>
      <td>0.483</td>
      <td>0.637</td>
      <td>0.737</td>
      <td>0.680</td>
    </tr>
    <tr>
      <td rowspan="2">Llama3<br>70B*</td>
      <td>SenLLM</td>
      <td>0.052</td>
      <td>0.411</td>
      <td>0.594</td>
      <td>0.630</td>
      <td>0.608</td>
    </tr>
    <tr>
      <td>AutoLife</td>
      <td>0.000</td>
      <td>0.505</td>
      <td><strong>0.650</strong></td>
      <td>0.738</td>
      <td>0.688</td>
    </tr>
  </tbody>
</table>

attending a conference or event. Interestingly, it derives that event is IoT-related from a scanned SSID "CPS-IoT WEEK 2024". Overall, the generated journal aligns well with the reference journal and their similarities achieve high BERTScore. Interestingly, we observe that LLMs sometimes give some complementary descriptions like "participation in sessions", which are valid but do not appear in the reference journals. Additionally, LLM can make some reasonable speculations based on the motion and location contexts, e.g., 'swimming'. Both factors typically result in the generated journal being longer than the reference journal, which causes the recall to be higher than the precision.

To provide a comprehensive quantitative evaluation, we test AutoLife and the baseline solution SensorLLM using different LLMs for journal generation, including GPT-4o [48], Claude 3 [5], Gemini 1.5 [54], and Llama3 [1]. Table 2 presents their overall performance across various metrics. Interestingly, we find that many LLMs within the SensorLLM

