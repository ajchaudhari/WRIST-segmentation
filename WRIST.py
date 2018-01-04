#############################################################################################

#############################################################################################

from __main__ import vtk, qt, ctk, slicer
import EditorLib

import SimpleITK as sitk
import sitkUtils
import numpy as np


import timeit


#
# BoneSegmentation
#
class WRIST:

    def __init__(self, parent):
        import string
        parent.title = "WRIST - Carpal Bone Segmentation"
        parent.categories = ["WRIST Segmentation"]
        parent.contributors = ["Brent Foster (University of California Davis)"]
        parent.helpText = """

        	WRIST-A WRist Image Segmentation Toolkit for Carpal Bone Delineation from MRI
        	<br>
        	<br>
        	Use this module to segment the eight carpal bones of the wrist from MRI. <br>
        	Input volume is the MR image. <br>
        	Output volume is the image to save the resulting segmentation to. <br>
        	<br>
        	HOW TO
        	<br>
        	(1) Select the input MRI and create a new output volume (for saving the image to).
        	<br>
        	(2) Use the 3D Slicer fiduicial marker tool to click once per bone.
        	<br>
        	(3) Select the markups list in the Markup List selector. 
        	<br>
        	(4) Click on the bone selection table on the bones of interest in the same order as the fiducial markers.
        	<br>
        	(5) Select male, female, or unknown if not known. (For basic prior shape information).
        	<br>
        	(6) Click on Compute button.
        	<br>
        	<br>

        	HINTS
        	<br>
        	(*) To improve segmentation result, select the "Show Filtered Image" checkmark on bottom. Then adjust the sigmoid threshold.
        	Choose a value which selects the bone edges without including too much background. 
        	<br>
        	(*) If leakage into the background, try reducing the propagation scale, lowering the initial maximum iterations, decreasing the anisotropic diffusion iterations, or adjusting sigmoid threshold. 
        	<br>
        	(*) If it's missing sections of the bone, try increasing anisotropic diffusion iterations (to reduce noise), increasing the propagation scale (more outward force on the level set), or adjusting sigmoid threshold. 
        	<br>
        	<br>
        	Please see the README and source code at https://github.com/ajchaudhari/WRIST-segmentation <br>
        	<br>
        	For details on the approach please see Foster et al. 'WRIST-A WRist Image Segmentation Toolkit for Carpal Bone Delineation from MRI' Computerized Medical Imaging and Graphics (2017).
        	"""

        parent.acknowledgementText = """

	        The authors acknowledge the following funding sources: National Science Foundation (NSF) GRFP Grant No. 1650042, and National Institutes of Health (NIH) grants: K12 HD051958 and R03 EB015099.
	        <br>
	        <br>
		    Please see the corresponding journal publication for details on the method.
		    <br>
		    <br>
		    Foster et al. 'WRIST-A WRist Image Segmentation Toolkit for Carpal Bone Delineation from MRI' Computerized Medical Imaging and Graphics (2017).


		    """
        self.parent = parent

class WRISTWidget:
    def __init__(self, parent=None):
        self.parent = parent
        self.logic = None
        self.ImageNode = None

        # Initilize the multiHelper class that is defined at the bottom of this file
        self.multiHelper = Multiprocessor()
        # Initilize a flag to stop the segmentation if the user hits the stop button
        self.multiHelper.segmentationClass = BoneSeg()
        self.multiHelper.segmentationClass.stop_segmentation = False


    def setup(self):
        frame = qt.QFrame()
        frameLayout = qt.QFormLayout()
        frame.setLayout(frameLayout)
        self.parent.layout().addWidget(frame)


        #
        # Input Volume Selector
        #
        self.inputVolumeSelectorLabel = qt.QLabel()
        self.inputVolumeSelectorLabel.setFont(qt.QFont('Arial', 12))
        self.inputVolumeSelectorLabel.setText("Input Volume: ")
        self.inputVolumeSelectorLabel.setToolTip(
            "Select the input volume to be segmented")
        self.inputSelector = slicer.qMRMLNodeComboBox()
        self.inputSelector.setFont(qt.QFont('Arial', 12))
        self.inputSelector.nodeTypes = ("vtkMRMLScalarVolumeNode", "")
        self.inputSelector.noneEnabled = False
        self.inputSelector.selectNodeUponCreation = True
        self.inputSelector.setMRMLScene(slicer.mrmlScene)
        frameLayout.addRow(
            self.inputVolumeSelectorLabel, self.inputSelector)
        self.inputSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onInputSelect)


        #
        # Output Volume Selector
        #
        self.outputVolumeSelectorLabel = qt.QLabel()
        self.outputVolumeSelectorLabel.setFont(qt.QFont('Arial', 12))
        self.outputVolumeSelectorLabel.setText("Output Volume: ")
        self.outputVolumeSelectorLabel.setToolTip(
            "Select the output volume to save to")
        self.outputSelector = slicer.qMRMLNodeComboBox()
        self.outputSelector.setFont(qt.QFont('Arial', 12))
        # self.outputSelector.nodeTypes = ("vtkMRMLScalarVolumeNode", "")
        self.outputSelector.nodeTypes = ["vtkMRMLLabelMapVolumeNode"]
        self.outputSelector.noneEnabled = False
        self.outputSelector.selectNodeUponCreation = True
        self.outputSelector.setMRMLScene(slicer.mrmlScene)
        frameLayout.addRow(
            self.outputVolumeSelectorLabel, self.outputSelector)
        # self.outputSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onInputSelect)


        #
        # Markup Selector
        #
        self.markupSelectorLabel = qt.QLabel()
        self.markupSelectorLabel.setFont(qt.QFont('Arial', 12))
        self.markupSelectorLabel.setText("Markup List: ")
        self.markupSelector = slicer.qMRMLNodeComboBox()
        self.markupSelector.setFont(qt.QFont('Arial', 12))
        self.markupSelector.nodeTypes = ("vtkMRMLMarkupsFiducialNode", "")
        self.markupSelector.noneEnabled = False
        self.markupSelector.baseName = "Seed List"
        self.markupSelector.selectNodeUponCreation = True
        self.markupSelector.setMRMLScene(slicer.mrmlScene)
        self.markupSelector.setToolTip("Pick the markup list of fiducial markers to use as initial points for the segmentation. (One marker for each object of interest)")
        frameLayout.addRow(self.markupSelectorLabel, self.markupSelector)
        self.markupSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onMarkupSelect)

        #
        # Bone Selection Table 
        #
        self.label = qt.QLabel()
        self.label.setFont(qt.QFont('Arial', 12))
        self.label.setText("Bone Selection: ")        
        self.ModuleList = qt.QTableWidget()
        self.ModuleList.verticalHeader().setVisible(False)
        self.ModuleList.horizontalHeader().setVisible(False)
        self.ModuleList.setRowCount(2)
        self.ModuleList.setColumnCount(4)
        self.ModuleList.setFont(qt.QFont('Arial', 12))
        self.ModuleList.setFixedHeight(75)        
        self.ModuleList.horizontalHeader().setResizeMode(qt.QHeaderView.Stretch)
        self.ModuleList.verticalHeader().setResizeMode(qt.QHeaderView.Stretch)
        self.ModuleList.selectionMode = qt.QAbstractItemView.MultiSelection
        self.ModuleList.horizontalHeader().setStretchLastSection(True)
        self.ModuleList.connect('itemSelectionChanged()', self.onModuleListChange)

        self.bone_list = [['Trapezium', 'Trapezoid', 'Scaphoid', 'Capitate'],['Lunate', 'Hamate', 'Triquetrum', 'Pisiform']]        
        self.Reset_Table_Widget()
        frameLayout.addRow(self.label, self.ModuleList)


        #
        # Flip Bone Selection Table Button
        #
        self.FlipTableFlag = 1 # Flag for remembering which orientation the table is currently in
        self.FlipTableButton = qt.QPushButton("Flip Table")
        self.FlipTableButton.setFont(qt.QFont('Arial', 12))
        self.FlipTableButton.toolTip = "Flip table left or right (for right or left hands)"
        frameLayout.addWidget(self.FlipTableButton)
        self.FlipTableButton.connect('clicked()', self.onFlipTableButton)


        #
        # Gender Selection Button
        #
        self.label = qt.QLabel()
        self.label.setFont(qt.QFont('Arial', 12))
        self.label.setText("Gender Selection: ")

        self.GenderSelectionList = qt.QListWidget()
        self.GenderSelectionList.selectionMode = qt.QAbstractItemView.SingleSelection
        self.GenderSelectionList.addItem('Male')
        self.GenderSelectionList.addItem('Female')
        self.GenderSelectionList.addItem('Unknown')
        self.GenderSelectionList.setFont(qt.QFont('Arial', 12))
        self.GenderSelectionList.setResizeMode(qt.QHeaderView.Stretch)
        self.GenderSelectionList.setFixedHeight(75)
        # self.GenderSelectionList.setFixedSize(100,75)

        frameLayout.addRow(self.label, self.GenderSelectionList)
        self.GenderSelectionList.connect('itemSelectionChanged()', self.onGenderSelectionListChange)


        #
        # Relaxation on Anatomical Prior Information
        #        
        self.label = qt.QLabel()
        self.label.setFont(qt.QFont('Arial', 12))
        self.label.setText("Anatomical Relaxation: ")
        self.label.setToolTip(
            "Select the relaxation on the prior anatomical knowledge contraint (e.g. 0.10 is 10 percent relaxation)")
        self.RelaxationSlider = ctk.ctkSliderWidget()
        self.RelaxationSlider.setFont(qt.QFont('Arial', 12))
        self.RelaxationSlider.minimum = 0
        self.RelaxationSlider.maximum = 1.0
        self.RelaxationSlider.value = 0.10

        self.RelaxationSlider.singleStep = 0.01
        self.RelaxationSlider.tickInterval = 0.01
        self.RelaxationSlider.decimals = 2


        self.RelaxationSlider.connect('valueChanged(double)', self.onRelaxationSliderChange)
        frameLayout.addRow(self.label, self.RelaxationSlider)
        #Set default value
        self.RelaxationAmount = self.RelaxationSlider.value


        #
        # Shape Detection Level set maximum Iterations
        #        
        self.label = qt.QLabel()
        self.label.setFont(qt.QFont('Arial', 12))                
        self.label.setText("Initial Maximum Iterations: ")
        self.label.setToolTip(
            "Select the maximum number of iterations for the shape detection level set convergence")
        self.ShapeMaxItsInputSlider = ctk.ctkSliderWidget()
        self.ShapeMaxItsInputSlider.setFont(qt.QFont('Arial', 12))
        self.ShapeMaxItsInputSlider.minimum = 0
        self.ShapeMaxItsInputSlider.maximum = 2500
        self.ShapeMaxItsInputSlider.value = 500
        self.ShapeMaxItsInputSlider.connect('valueChanged(double)', self.onShapeMaxItsInputSliderChange)
        frameLayout.addRow(self.label, self.ShapeMaxItsInputSlider)
        #Set default value
        self.ShapeMaxIts = self.ShapeMaxItsInputSlider.value


        #
        # Shape Detection Level set maximum RMS error slider
        #        
        self.label = qt.QLabel()
        self.label.setFont(qt.QFont('Arial', 12))
        self.label.setText("Maximum RMS Error: ")
        self.label.setToolTip(
            "Select the maximum root mean square error to determine convergence of the shape detection level set filter")
        self.ShapeMaxRMSErrorInputSlider = ctk.ctkSliderWidget()
        self.ShapeMaxRMSErrorInputSlider.setFont(qt.QFont('Arial', 12))
        self.ShapeMaxRMSErrorInputSlider.minimum = 0.001
        self.ShapeMaxRMSErrorInputSlider.maximum = 0.15
        self.ShapeMaxRMSErrorInputSlider.value = 0.003
        self.ShapeMaxRMSErrorInputSlider.singleStep = 0.001
        self.ShapeMaxRMSErrorInputSlider.tickInterval = 0.001
        self.ShapeMaxRMSErrorInputSlider.decimals = 3
        self.ShapeMaxRMSErrorInputSlider.connect('valueChanged(double)', self.onShapeMaxRMSErrorInputSliderChange)
        frameLayout.addRow(self.label, self.ShapeMaxRMSErrorInputSlider)
        #Set default value
        self.ShapeMaxRMSError = self.ShapeMaxRMSErrorInputSlider.value




        #
        # Shape Detection Level set curvatuve scale
        #        
        self.label = qt.QLabel()
        self.label.setFont(qt.QFont('Arial', 12))
        self.label.setText("Curvature Scale: ")
        self.label.setToolTip(
            "Select the shape curvature scale (higher number causes more smoothing)")
        self.ShapeCurvatureScaleInputSlider = ctk.ctkSliderWidget()
        self.ShapeCurvatureScaleInputSlider.setFont(qt.QFont('Arial', 12))
        self.ShapeCurvatureScaleInputSlider.minimum = 0
        self.ShapeCurvatureScaleInputSlider.maximum = 3
        self.ShapeCurvatureScaleInputSlider.value = 1
        self.ShapeCurvatureScaleInputSlider.singleStep = 0.01
        self.ShapeCurvatureScaleInputSlider.tickInterval = 0.01
        self.ShapeCurvatureScaleInputSlider.decimals = 1
        self.ShapeCurvatureScaleInputSlider.connect('valueChanged(double)', self.onShapeCurvatureScaleInputSliderChange)
        frameLayout.addRow(self.label, self.ShapeCurvatureScaleInputSlider)
        #Set default value
        self.ShapeCurvatureScale = self.ShapeCurvatureScaleInputSlider.value


        #
        # Shape Detection Level set propagation scale
        #        
        self.label = qt.QLabel()
        self.label.setFont(qt.QFont('Arial', 12))
        self.label.setText("Propagation Scale: ")
        self.label.setToolTip(
            "Select the shape curvature scale (higher number causes more smoothing)")
        self.ShapePropagationScaleInputSlider = ctk.ctkSliderWidget()
        self.ShapePropagationScaleInputSlider.setFont(qt.QFont('Arial', 12))
        self.ShapePropagationScaleInputSlider.minimum = 0
        self.ShapePropagationScaleInputSlider.maximum = 5
        self.ShapePropagationScaleInputSlider.value = 4
        self.ShapePropagationScaleInputSlider.singleStep = 0.2
        self.ShapePropagationScaleInputSlider.tickInterval = 0.2
        self.ShapePropagationScaleInputSlider.decimals = 1
        self.ShapePropagationScaleInputSlider.connect('valueChanged(double)', self.onShapePropagationScaleInputSliderChange)
        frameLayout.addRow(self.label, self.ShapePropagationScaleInputSlider)
        # Set default value
        self.ShapePropagationScale = self.ShapePropagationScaleInputSlider.value


        #
        # Anisotropic Diffusion Iterations 
        # 
        self.label = qt.QLabel()
        self.label.setFont(qt.QFont('Arial', 12))
        self.label.setText("Anisotropic Diffusion Its: ")
        self.label.setToolTip(
            "Select the number of iterations for the Anisotropic Diffusion filter for image denoising.")
        self.DiffusionItsSlider = ctk.ctkSliderWidget()
        self.DiffusionItsSlider.setFont(qt.QFont('Arial', 12))
        self.DiffusionItsSlider.minimum = 0
        self.DiffusionItsSlider.maximum = 25
        self.DiffusionItsSlider.value = 5
        self.DiffusionItsSlider.connect('valueChanged(double)', self.onDiffusionItsSliderChange)
        frameLayout.addRow(self.label, self.DiffusionItsSlider)
        # Set default value
        self.DiffusionIts = self.DiffusionItsSlider.value

        
        #
        # Sigmoid threshold slider
        #
        self.label = qt.QLabel()
        self.label.setFont(qt.QFont('Arial', 12))
        self.label.setText("Sigmoid Threshold: ")
        self.label.setToolTip(
            "Select the threshold that the sigmoid filter will use. Set to 0 to try to automatically find a good value.")
        self.SigmoidInputSlider = ctk.ctkSliderWidget()
        self.SigmoidInputSlider.setFont(qt.QFont('Arial', 12))
        self.SigmoidInputSlider.minimum = 0
        self.SigmoidInputSlider.maximum = 300
        self.SigmoidInputSlider.value = 0
        self.SigmoidThreshold = self.SigmoidInputSlider.value
        self.SigmoidInputSlider.connect('valueChanged(double)', self.onSigmoidInputSliderChange)
        frameLayout.addRow(self.label, self.SigmoidInputSlider)


       
        #
        # Compute button
        #
        self.computeButton = qt.QPushButton("Compute")
        self.computeButton.setFont(qt.QFont('Arial', 12))
        self.computeButton.toolTip = "Compute the segmentation"
        self.computeButton.setFixedHeight(50)
        frameLayout.addWidget(self.computeButton)
        self.UpdatecomputeButtonState()
        self.computeButton.connect('clicked()', self.onCompute)

        #
        # Stop button
        #
        self.stopButton = qt.QPushButton("Stop")
        self.stopButton.setFont(qt.QFont('Arial', 12))
        self.stopButton.toolTip = "Cancel the currently running segmentation."
        self.stopButton.setFixedHeight(25)
        frameLayout.addWidget(self.stopButton)
        self.stopButton.connect('clicked()', self.onStopButton)


        #
        # Show Filtered Image Checkmark
        #
        self.show_filtered_image = qt.QCheckBox("Show Filtered Image")
        self.show_filtered_image.toolTip = "When checked, show the filtered image (when adjusting the Sigmoid Threshold slider)."
        self.show_filtered_image.checked = False
        frameLayout.addWidget(self.show_filtered_image) 

        #
        # Dilate Final Segmentation
        #
        self.dilate_image = qt.QCheckBox("Dilate Final Image")
        self.dilate_image.toolTip = "When checked, dilate the final segmentation result. Useful if the segmentation boundary is uniformly a bit too small."
        self.dilate_image.checked = True
        frameLayout.addWidget(self.dilate_image) 

        #
        # Flip Seed XY Checkmark
        #
        self.flip_seed_XY = qt.QCheckBox("Flip Seed XY")
        self.flip_seed_XY.toolTip = "When checked, flip the XY coordinates of the seed locations. Useful if the image is not in standard RAS orientation. Alternatively, when loading the image into Slicer could do the ignore orientation option."
        self.flip_seed_XY.checked = False
        frameLayout.addWidget(self.flip_seed_XY) 

        #
        # Flip Sigmoid Checkmark
        #
        self.flip_sigmoid = qt.QCheckBox("Flip Sigmoid")
        self.flip_sigmoid.toolTip = "When checked, the image to segment has the bones with a higher intensity (whiter) while the background is darker. Useful for certain MRI sequences and potentially for CT."
        self.flip_sigmoid.checked = False
        frameLayout.addWidget(self.flip_sigmoid) 


    def onStopButton(self):
    	# Attempt to stop the currently running segmentation
    	# Useful if the user sees the first bone segmented is not going well

    	slicer.app.processEvents()
    	self.multiHelper.segmentationClass.stop_segmentation = True


    def Reset_Table_Widget(self):
        # Reset the bone labels in the table widget
        # self.bone_list = [['Trapezium', 'Trapezoid', 'Scaphoid', 'Capitate'],['Lunate', 'Hamate', 'Triquetrum', 'Pisiform']]

        for i in range(0,2):
            for j in range(0,4):
                item = qt.QTableWidgetItem()
                item.setText(self.bone_list[i][j])
                self.ModuleList.setItem(i,j,item)

    def onFlipTableButton(self):
        # Flip the table which is uesd to select which bones and in which order the initial seed locations
        # were chosen in. This is needed in left vs. right hands for example (mirror images of each other)

        if self.FlipTableFlag == 0:
            self.bone_list = [['Trapezium', 'Trapezoid', 'Capitate', 'Hamate'],['Scaphoid', 'Lunate', 'Triquetrum', 'Pisiform']]
            self.FlipTableFlag = 1
        elif self.FlipTableFlag == 1:
            self.bone_list = [['Hamate', 'Capitate', 'Trapezoid', 'Trapezium'],['Pisiform', 'Triquetrum', 'Lunate', 'Scaphoid']]
            self.FlipTableFlag = 0

        # Reset the table now that the bone list has flipped
        self.Reset_Table_Widget()

    def onDiffusionItsSliderChange(self, newValue):
		self.DiffusionIts = newValue

		# Update the image to show how changing the parameter affects the image preprocessing
		if self.show_filtered_image.checked == True:	

			self.anisotropicFilter = sitk.CurvatureAnisotropicDiffusionImageFilter()
			self.anisotropicFilter.SetNumberOfIterations(int(self.DiffusionIts))
			self.anisotropicFilter.SetTimeStep(0.02) # Default values
			self.anisotropicFilter.SetConductanceParameter(2) # Default values

			# Find the input image in Slicer and convert to a SimpleITK image type
			imageID = self.inputSelector.currentNode()
			image = sitkUtils.PullFromSlicer(imageID.GetName())

			# Cast the original_image to UInt 16 just to be safe
			image = sitk.Cast(image, sitk.sitkFloat32)


			image = self.anisotropicFilter.Execute(image)



			# Create a new image named Filtered to hold the filtered image
			# Check to see if we've already created an image named Filtered
			# Create one if we haven't yet
			try:
				sitkUtils.PullFromSlicer('AD_Filtered')
			except:
				self.Filtered = slicer.vtkMRMLScalarVolumeNode()
				self.Filtered.SetName('AD_Filtered')
				slicer.mrmlScene.AddNode(self.Filtered)

			sitkUtils.PushVolumeToSlicer(image, targetNode=self.Filtered, name='AD_Filtered', className='vtkMRMLScalarVolumeNode')
			slicer.util.setSliceViewerLayers(background='keep-current', foreground=self.Filtered, label='keep-current', foregroundOpacity=0.5, labelOpacity=1)

    def onGenderSelectionListChange(self):
        self.selected_gender = self.GenderSelectionList.currentItem().text()
        print('self.selected_gender')
        print(self.selected_gender)

    def onModuleListChange(self):
        # Reset the table first!
        self.Reset_Table_Widget()

        ndx = self.ModuleList.selectedIndexes()
        self.BonesSelected = []

        for i in range(0,len(ndx)):
            item = qt.QTableWidgetItem()
            
            row = ndx[i].row()
            column = ndx[i].column()

            # Add one here to make it more intuitive then starting at 0
            curr_bone = self.bone_list[row][column]
            item.setText(curr_bone + ' ' + str(i+1))


            self.ModuleList.setItem(row,column,item)

            self.BonesSelected.append(curr_bone)

        print('BonesSelected')
        print(self.BonesSelected)
        print(' ')        

    def onSigmoidInputSliderChange(self, newValue):
		self.SigmoidThreshold = newValue

		# Update the image to show how changing the parameter affects the image preprocessing
		if self.show_filtered_image.checked == True:			
			# Sigmoid SimpleITK Filter
			sigFilter = sitk.SigmoidImageFilter()

			# Check to see if we're segmenting bright or dark bones on the image
			# By checking the flag of the checkmark on the user interface
			if self.flip_sigmoid.checked == False:
				sigFilter.SetAlpha(0)
				sigFilter.SetBeta(int(self.SigmoidThreshold))
				self.SigmoidInputSlider.maximum = 300
			else:
				sigFilter.SetAlpha(int(self.SigmoidThreshold))
				sigFilter.SetBeta(0)
				self.SigmoidInputSlider.maximum = 3000

			sigFilter.SetOutputMinimum(0)
			sigFilter.SetOutputMaximum(255)


			# Find the input image in Slicer and convert to a SimpleITK image type
			imageID = self.inputSelector.currentNode()
			image = sitkUtils.PullFromSlicer(imageID.GetName())

			processedImage  = sigFilter.Execute(image) 
			processedImage  = sitk.Cast(processedImage, sitk.sitkUInt16)


			gradientFilter = sitk.GradientImageFilter()
			gradImage = gradientFilter.Execute(processedImage)

			edgePotentialFilter = sitk.EdgePotentialImageFilter()		
			processedImage = edgePotentialFilter.Execute(gradImage)

			EdgePotentialMap = sitk.Cast(processedImage, sitk.sitkFloat32)


			# Create a new image named Filtered to hold the filtered image
			# Check to see if we've already created an image named Filtered
			# Create one if we haven't yet
			try:
				sitkUtils.PullFromSlicer('Filtered')
			except:
				self.Filtered = slicer.vtkMRMLScalarVolumeNode()
				self.Filtered.SetName('Filtered')
				slicer.mrmlScene.AddNode(self.Filtered)

			sitkUtils.PushVolumeToSlicer(EdgePotentialMap, targetNode=self.Filtered, name='Filtered', className='vtkMRMLScalarVolumeNode')
			slicer.util.setSliceViewerLayers(background='keep-current', foreground=self.Filtered, label='keep-current', foregroundOpacity=0.5, labelOpacity=1)

    def onRelaxationSliderChange(self, newValue):
        self.RelaxationAmount = newValue

    def onNumScalingSliderChange(self, newValue):
        self.NumScaling = newValue

    def onWindowScalingSliderChange(self, newValue):
        self.WindowScaling = newValue

    def onShapePropagationScaleInputSliderChange(self, newValue):
        self.ShapePropagationScale = newValue

    def onShapeCurvatureScaleInputSliderChange(self, newValue):
        self.ShapeCurvatureScale = newValue

    def onShapeMaxItsInputSliderChange(self, newValue):
        self.ShapeMaxIts = newValue

    def onShapeMaxRMSErrorInputSliderChange(self, newValue):
        self.ShapeMaxRMSError = newValue

    def onMaxRMSErrorInputSliderChange(self, newValue):
        self.MaxRMSError = newValue

    def onMaxItsInputSliderChange(self, newValue):
        self.MaxIts = newValue

    def onthresholdInputSliderRelease(self, newLowerThreshold, newUpperThreshold):
        self.LevelSetThresholds = (newLowerThreshold, newUpperThreshold)

    def onNumCPUChange(self, newValue):
        self.NumCPUs = newValue

    def UpdatecomputeButtonState(self):
        #Enable the 'Compute' button only if there is a selection to the input volume and markup list
        if not self.markupSelector.currentNode():
            self.computeButton.enabled = False
        elif self.inputSelector.currentNode():
            self.computeButton.enabled = True
        else:
            self.computeButton.enabled = False

    def onInputSelect(self, node):
        #Test to see if the Compute button should be enabled/disabled
        self.UpdatecomputeButtonState()
        # self.ImageNode = node

    def onMarkupSelect(self, node):
        #Test to see if the Compute button should be enabled/disabled
        self.UpdatecomputeButtonState()

    def onCompute(self):
    	# Flip the flag on the stop segmentation button 
    	self.multiHelper.segmentationClass.stop_segmentation = False

    	# Set the flag for the flip sigmoid for the segmentation class
    	self.multiHelper.segmentationClass.flip_sigmoid = self.flip_sigmoid.checked

    	# Move the current state of the flip seed XY flag to the segmentation class object
    	self.multiHelper.segmentationClass.flip_seed_XY = self.flip_seed_XY.checked

        slicer.app.processEvents()

        # Find the output image in Slicer to save the segmentation to
        imageID = self.outputSelector.currentNode()
        imageID.GetName() # Give error if there is no output volume selected


        # TODO: Consider adding a QProgressBar() if not too difficult
        # Make a list of all the seed point locations
        fidList = self.markupSelector.currentNode()
        numFids = fidList.GetNumberOfFiducials()
        seedPoints = []
        # Create a list of the fiducial markers from the 'Markup List' input
        for i in range(numFids):
            ras = [0,0,0]
            fidList.GetNthFiducialPosition(i,ras)
            seedPoints.append(ras)
        print(fidList)

        # Find the input image in Slicer and convert to a SimpleITK image type
        imageID = self.inputSelector.currentNode()
        image = sitkUtils.PullFromSlicer(imageID.GetName())

        # Slicer has the fiducial markers in physical coordinate space, but need to have the po0ints in voxel space
        # Convert using a SimpleITk function   
        for i in range(numFids):

        	if self.flip_seed_XY.checked == True:
        		# Image is not in the standard RAS format so multiply the X and Y by negative one
        		seedPoints[i] = image.TransformPhysicalPointToContinuousIndex([-1*seedPoints[i][0], -1*seedPoints[i][1], seedPoints[i][2]])
        	else:
        		seedPoints[i] = image.TransformPhysicalPointToContinuousIndex([seedPoints[i][0], seedPoints[i][1], seedPoints[i][2]])

        		# Need to multiply the first two coordinates by negative one (because how Slicer interprets the coordinate system)
        		seedPoints[i] = np.asarray(seedPoints[i])
        		seedPoints[i][0] = -1*seedPoints[i][0]
        		seedPoints[i][1] = -1*seedPoints[i][1]


    		print('seedPoints[i]')
    		print(seedPoints[i])
    		



            # print(image.TransformPhysicalPointToContinuousIndex([seedPoints[i][0], seedPoints[i][0], seedPoints[i][0]]))
            # print(image.TransformPhysicalPointToContinuousIndex([seedPoints[i][1], seedPoints[i][1], seedPoints[i][1]]))
            # print(image.TransformPhysicalPointToContinuousIndex([seedPoints[i][2], seedPoints[i][2], seedPoints[i][2]]))

            # print(image.TransformPhysicalPointToContinuousIndex([-1*seedPoints[i][0], -1*seedPoints[i][0], -1*seedPoints[i][0]]))
            # print(image.TransformPhysicalPointToContinuousIndex([-1*seedPoints[i][1], -1*seedPoints[i][1], -1*seedPoints[i][1]]))
            # print(image.TransformPhysicalPointToContinuousIndex([-1*seedPoints[i][2], -1*seedPoints[i][2], -1*seedPoints[i][2]]))


        # Initilize the two classes that are defined at the bottom of this file
        # import BoneSegmentation
        # segmentationClass = BoneSegmentation.BoneSeg()
        # self.multiHelper = Multiprocessor()

        parameters = [self.ShapeCurvatureScale, self.ShapeMaxRMSError, self.ShapeMaxIts, 
                        self.ShapePropagationScale, self.selected_gender, self.BonesSelected, self.RelaxationAmount,
                        self.DiffusionIts, self.dilate_image.checked, self.SigmoidThreshold] 
       
        NumCPUs = 1
        Segmentation = self.multiHelper.Execute(seedPoints, image, parameters, NumCPUs, self.outputSelector, True)

        slicer.app.processEvents()

        # Output options in Slicer = {0:'background', 1:'foreground', 2:'label'}
        imageID = self.outputSelector.currentNode()
        sitkUtils.PushVolumeToSlicer(Segmentation, targetNode=imageID,name=imageID.GetName(), className='vtkMRMLLabelMapVolumeNode')# 
        slicer.util.setSliceViewerLayers(background='keep-current', foreground='keep-current', label=imageID, foregroundOpacity=None, labelOpacity=1)


class BoneSeg(object):
    """Class of BoneSegmentation. REQUIRED: BoneSeg(MRI_Image,SeedPoint)"""
    def Execute(self, original_image, original_seedPoint, verbose=False, returnSitkImage=True, convertSeedPhyscialFlag=True):


        start_time = timeit.default_timer()

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

        self.verbose = verbose # Optional argument to output text to terminal

        self.image = original_image
        self.original_image = original_image
        self.seedPoint = original_seedPoint
        self.convertSeedPhyscialFlag = convertSeedPhyscialFlag
        self.returnSitkImage = returnSitkImage        

        # Convert images to type float 32 first
        try:
            self.image = sitk.Cast(self.image, sitk.sitkFloat32)
        except:
            # Convert from numpy array to a SimpleITK image type first then cast
            self.image = sitk.Cast(sitk.GetImageFromArray(self.image), sitk.sitkFloat32)
            self.original_image = self.image # original_image needs to be a SimpleITK image type for later

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

        # Cast the original_image to UInt 16 just to be safe
        self.original_image = sitk.Cast(self.original_image, sitk.sitkUInt16)

        # Define what the anatimical prior volume and bounding box is for each carpal bone
        self.DefineAnatomicPrior()

        if self.verbose == True:
            print(' ')
            print('\033[94m' + "Current Seed Point: "),
            print(self.seedPoint)
            print(' ')
            print('\033[94m' + "Rounding and converting to voxel domain: "), 

        # Convert the seed point to image coordinates (from physical) if needed and round
        self.RoundSeedPoint()

        if self.verbose == True:
            print(' ')
            print('\033[94m' + 'Estimating upper sigmoid threshold level')

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

        # Estimate the threshold level by image intensity statistics
        # Skip if the user selected a lower threshold already
        if self.SkipTresholdCalculation == False:        	
            LowerThreshold = self.EstimateSigmoid()
            asdasd
            if self.verbose == True:
                print(' ')
                print('\033[94m' + 'LowerThreshold:' + str(LowerThreshold))
            self.SetLevelSetLowerThreshold(LowerThreshold)

        # Crop the image so that it considers only a search space around the seed point
        # to speed up computation significantly!
        if self.verbose == True:
            print(' ')
            print('\033[94m' + 'Cropping image')
        self.CropImage()
        # sitk.Show(self.image, 'Post-cropping')

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return


        if self.verbose == True:
            print(' ')
            print('\033[94m' + 'Applying Anisotropic Filter')
        self.apply_AnisotropicFilter()
        # sitk.Show(self.image, 'Post-Anisotropic')

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

        if self.verbose == True:
            elapsed = timeit.default_timer() - start_time
            print(' ')
            print("Elapsed Time (Preprocessing ):" + str(round(elapsed,3)))
    
        # Preprocess the level set (only need to do this once)
        if self.verbose == True:
            print(' ')
            print('\033[94m' + 'Preprocess Level Set')
        self.PreprocessLevelSet()

        # Initialize the level set (creates the image for saving the levelset using the seed location)
        if self.verbose == True:
            print(' ')
            print('\033[94m' + 'Initializing the Level Set')
        self.InitializeLevelSet()


        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return


        if self.verbose == True:
            print(' ')
            print('\033[90m' + "Sigmoid shape detection level set by iteration...")
        self.SigmoidLevelSetIterations()
        
        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

        if self.verbose == True:
            print(' ')
            print('\033[96m' + "Finished with seed point "),
            print(self.seedPoint)

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

        if self.verbose == True:
            print(' ')
            print('\033[93m' + "Running Leakage Check...")
        # Don't run leakage check if relaxation is 100%

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

        if self.AnatomicalRelaxation != 1:
        	# Initilize a variable to hold the number of iterations of the 
        	# leakage check run
        	self.LeakageCheck_iterations = 0
        	# Save the seed point location now (possibly needed for finding a random seed location later)
        	self.seedPoint_converted = self.seedPoint 

        	self.LeakageCheck()

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

        # if self.verbose == True:
        #     print(' ')
        #     print('\033[93m' + "Filling Any Holes...")
        # Fill holes prior to uncropping image for much faster computation
        # self.HoleFilling()

        # if self.verbose == True:
        #     print(' ')
        #     print('\033[93m' + "Smoothing Label...")
        # self.SmoothLabel()

        # Dilating by same radius if the user selected the checkmark in the GUI
        if self.DilateImage == True:
        	if self.verbose == True:
        		print(' ')        		
        		print('\033[93m' + "Dilating the Segmentation...")

    		# Cast to 16 bit (needed for the fill filter to work)
    		self.segImg  = sitk.Cast(self.segImg, sitk.sitkUInt16)
    		self.dilateFilter.SetKernelRadius(1)
    		self.segImg = self.dilateFilter.Execute(self.segImg, 0, 1, False)



        if self.verbose == True:
            print(' ')
            print('\033[93m' + "Changing Label Value...")
        self.ChangeLabelValue()

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return


        if self.verbose == True:
            print(' ')
            print('\033[90m' + "Uncropping Image...")
        self.UnCropImage()
        
        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return


        if self.verbose == True:
            print(' ')
            print('\033[97m' + "Exporting Final Segmentation...")
            print(' ')

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

        if self.returnSitkImage == True:        	
            # Check the image type first
            self.segImg = sitk.Cast(self.segImg, original_image.GetPixelID())
            print('RETURNING IMAGE TO SLICER')

            # Return a SimpleITK type image
            return  self.segImg 
        else:
            # Return a numpy array image (needed for using multiple logical cores)
            self.segImg.CopyInformation(self.original_image)
            self.segImg = sitk.Cast(self.segImg, sitk.sitkUInt8)
            npImg = sitk.GetArrayFromImage(self.segImg)

            return  npImg

    def ChangeLabelValue(self):
        BoneList = ['Trapezium', 'Trapezoid', 'Scaphoid', 'Capitate', 'Lunate', 'Hamate', 'Triquetrum', 'Pisiform']

        ndx = BoneList.index(self.current_bone)

        # Add one to the ndx because index starts at 0 instead of 1
        ndx = ndx + 1 

        npImg = sitk.GetArrayFromImage(self.segImg)

        print(' For bone ' + self.current_bone)
        print('Unique of npImg is ' + str(np.unique(npImg)))

        npImg[npImg != 0] = ndx

        print('Unique of npImg is now ' + str(np.unique(npImg)))

        # Convert back to SimpleITK image type
        tempImg = sitk.Cast(sitk.GetImageFromArray(npImg), sitk.sitkUInt16)
        tempImg.CopyInformation(self.segImg)

        self.segImg = tempImg

        return self

    def SmoothLabel(self):
        # Smooth the segmentation label image to reduce high frequency artifacts on the boundary
        SmoothFilter = sitk.DiscreteGaussianImageFilter()

        SmoothFilter.SetVariance(0.01)

        self.segImg = SmoothFilter.Execute(self.segImg)

        return self

    def SetDefaultValues(self):
        # Set the default values of all the parameters here
        self.SetScalingFactor(1) #X,Y,Z
       
        self.SeedListFilename = "PointList.txt"
        self.SetMaxVolume(300000) #Pixel counts (TODO change to mm^3) 

        # Anisotropic Diffusion Filter
        self.SetAnisotropicIts(5)
        self.SetAnisotropicTimeStep(0.02)
        self.SetAnisotropicConductance(2)

        # Morphological Operators
        self.fillFilter.SetForegroundValue(1) 
        self.fillFilter.FullyConnectedOff() 
        self.SetBinaryMorphologicalRadius(1)

        # Shape Detection Filter
        self.SetShapeMaxRMSError(0.004)
        self.SetShapeMaxIterations(400)
        self.SetShapePropagationScale(4)
        self.SetShapeCurvatureScale(1)

        # Sigmoid Filter
        self.sigFilter.SetAlpha(0)
        self.sigFilter.SetBeta(120)
        self.sigFilter.SetOutputMinimum(0)
        self.sigFilter.SetOutputMaximum(255)

        # Search Space Window
        # self.SetSearchWindowSize(50)

        # Set current bone and patient gender group
        self.SetCurrentBone('Capitate')
        self.SetPatientGender('Unknown')

        # Set the relaxation on the prior anatomical knowledge contraint
        self.SetAnatomicalRelaxation(0.15)

    def DefineAnatomicPrior(self):
        # The prior anatomical knowledge on the bone volume and dimensions is addeded
        # from Crisco et al. Carpal Bone Size and Scaling in Men Versus Women. J Hand Surgery 2005

        if self.PatientGender == 'Unknown':
            self.Prior_Volumes = {
            'Scaphoid-vol':[2390,673], 'Scaphoid-x':[27, 3.1], 'Scaphoid-y':[16.5,1.8], 'Scaphoid-z':[13.1,1.2], 
            'Lunate-vol':[1810,578], 'Lunate-x':[19.4, 2.3], 'Lunate-y':[18.5,2.2], 'Lunate-z':[13.2,1.7], 
            'Triquetrum-vol':[1341,331], 'Triquetrum-x':[19.7,2], 'Triquetrum-y':[18.5,2.2], 'Triquetrum-z':[13.2,1.7], 
            'Pisiform-vol':[712,219], 'Pisiform-x':[14.7,1.7], 'Pisiform-y':[11.5,1.4], 'Pisiform-z':[9.5,1.1], 
            'Trapezium-vol':[1970,576], 'Trapezium-x':[23.6,2.5], 'Trapezium-y':[16.6,1.8], 'Trapezium-z':[14.6,2.2], 
            'Trapezoid-vol':[1258,321], 'Trapezoid-x':[19.3,1.8], 'Trapezoid-y':[114.4,1.5], 'Trapezoid-z':[11.7,1.0], 
            'Capitate-vol':[3123,743], 'Capitate-x':[26.3,2.3], 'Capitate-y':[19.5,1.9], 'Capitate-z':[15,1.6],  
            'Hamate-vol':[2492,555], 'Hamate-x':[26.1,2.2], 'Hamate-y':[21.6,2], 'Hamate-z':[16,1.4]
            }
        elif self.PatientGender == 'Male':
            self.Prior_Volumes = {
            'Scaphoid-vol':[2903,461], 'Scaphoid-x':[29.3, 2.7], 'Scaphoid-y':[17.8,1.2], 'Scaphoid-z':[14.1,0.9], 
            'Lunate-vol':[2252,499], 'Lunate-x':[20.9,2.2], 'Lunate-y':[20.1,1.8], 'Lunate-z':[14.4,1.3], 
            'Triquetrum-vol':[1579,261], 'Triquetrum-x':[20.9,1.8], 'Triquetrum-y':[14.9,0.7], 'Triquetrum-z':[12.6,0.9], 
            'Pisiform-vol':[854,203], 'Pisiform-x':[15.7,1.4], 'Pisiform-y':[12.3,1.3], 'Pisiform-z':[10,1.2], 
            'Trapezium-vol':[2394,443], 'Trapezium-x':[25.4,1.8], 'Trapezium-y':[17.5,1.8], 'Trapezium-z':[16.1,1.8], 
            'Trapezoid-vol':[1497,237], 'Trapezoid-x':[20.6,1.4], 'Trapezoid-y':[15.5,0.8], 'Trapezoid-z':[12.3,0.7], 
            'Capitate-vol':[3700,563], 'Capitate-x':[28,1.8], 'Capitate-y':[20.8,1.7], 'Capitate-z':[16,1.6],  
            'Hamate-vol':[2940,378], 'Hamate-x':[27.5,1.9], 'Hamate-y':[23,1.8], 'Hamate-z':[16.9,1.2]
            }
        elif self.PatientGender == 'Female':
            self.Prior_Volumes = {
            'Scaphoid-vol':[1877,407], 'Scaphoid-x':[24.8,1.6], 'Scaphoid-y':[15.3,1.5], 'Scaphoid-z':[12.2,0.6], 
            'Lunate-vol':[1368,165], 'Lunate-x':[18,1.1], 'Lunate-y':[16.9,0.8], 'Lunate-z':[11.9,0.8], 
            'Triquetrum-vol':[1103,193], 'Triquetrum-x':[18.5,1.3], 'Triquetrum-y':[13.3,0.6], 'Triquetrum-z':[10.8,0.7], 
            'Pisiform-vol':[569,121], 'Pisiform-x':[13.7,1.4], 'Pisiform-y':[10.7,1], 'Pisiform-z':[8.9,0.7], 
            'Trapezium-vol':[1547,328], 'Trapezium-x':[21.8,1.8], 'Trapezium-y':[15.8,1.5], 'Trapezium-z':[13.1,1.2], 
            'Trapezoid-vol':[1020,191], 'Trapezoid-x':[18,0.9], 'Trapezoid-y':[13.3,1.2], 'Trapezoid-z':[11.1,0.8], 
            'Capitate-vol':[2547,344], 'Capitate-x':[24.6,1.1], 'Capitate-y':[18.2,1], 'Capitate-z':[13.9,0.8],  
            'Hamate-vol':[2045,264], 'Hamate-x':[24.7,1.4], 'Hamate-y':[20.1,0.8], 'Hamate-z':[15,0.9]
            }
        else:
            # Raise an erorr since 
            raise ValueError('Patient gender must be either "Male", "Female", or "Unknown". Value given was ' + self.PatientGender)


        # Allow some relaxation around the anatomical prior knowledge contraint
        # Calculate what the ranges should be for each measure using average and standard deviation and relaxation term
        self.lower_range_volume = (self.Prior_Volumes[self.current_bone + '-vol'][0] - self.Prior_Volumes[self.current_bone + '-vol'][1])*(1-self.AnatomicalRelaxation)
        self.upper_range_volume = (self.Prior_Volumes[self.current_bone + '-vol'][0] + self.Prior_Volumes[self.current_bone + '-vol'][1])*(1+self.AnatomicalRelaxation)

        self.lower_range_x = (self.Prior_Volumes[self.current_bone + '-x'][0] - self.Prior_Volumes[self.current_bone + '-x'][1])*(1-self.AnatomicalRelaxation)
        self.upper_range_x = (self.Prior_Volumes[self.current_bone + '-x'][0] + self.Prior_Volumes[self.current_bone + '-x'][1])*(1+self.AnatomicalRelaxation)

        self.lower_range_y = (self.Prior_Volumes[self.current_bone + '-y'][0] - self.Prior_Volumes[self.current_bone + '-y'][1])*(1-self.AnatomicalRelaxation)
        self.upper_range_y = (self.Prior_Volumes[self.current_bone + '-y'][0] + self.Prior_Volumes[self.current_bone + '-y'][1])*(1+self.AnatomicalRelaxation)

        self.lower_range_z = (self.Prior_Volumes[self.current_bone + '-z'][0] - self.Prior_Volumes[self.current_bone + '-z'][1])*(1-self.AnatomicalRelaxation)
        self.upper_range_z = (self.Prior_Volumes[self.current_bone + '-z'][0] + self.Prior_Volumes[self.current_bone + '-z'][1])*(1+self.AnatomicalRelaxation)

        # Use the bounding box ranges to create a suitable search window for the current particular carpal bone 
        self.searchWindow = np.rint(np.asarray([self.upper_range_x, self.upper_range_y, self.upper_range_z]))

        # Make the search window larger since the seed location won't be exactly in the center of the bone
        self.searchWindow = np.rint((2+self.AnatomicalRelaxation*2)*self.searchWindow)

        if self.verbose == True:
            print('\033[93m'  + 'Estimated Search Window is ' + str(self.searchWindow))
            print(' ')

        return self

    def ConnectedComponent(self):

        self.segImg = sitk.Cast(self.segImg, 1) #Can't be a 32 bit float
        # self.segImg.CopyInformation(segmentation)

        # Try to remove leakage areas by first eroding the binary and
        # get the labels that are still connected to the original seed location

        # self.segImg = self.erodeFilter.Execute(self.segImg, 0, 1, False)

        # self.segImg = self.connectedComponentFilter.Execute(self.segImg)

        # nda = sitk.GetArrayFromImage(self.segImg)
        # nda = np.asarray(nda)

        # # In numpy an array is indexed in the opposite order (z,y,x)
        # tempseedPoint = self.seedPoint[0]
        # val = nda[tempseedPoint[2]][tempseedPoint[1]][tempseedPoint[0]]

        # # Keep only the label that intersects with the seed point
        # nda[nda != val] = 0 
        # nda[nda != 0] = 1

        # self.segImg = sitk.GetImageFromArray(nda)

        # Undo the earlier erode filter by dilating by same radius
        # self.dilateFilter.SetKernelRadius(3)
        # self.segImg = self.dilateFilter.Execute(self.segImg, 0, 1, False)

        self.segImg = self.fillFilter.Execute(self.segImg)

        # self.segImg = self.erodeFilter.Execute(self.segImg, 0, 1, False)

        

        return self

    def HoleFilling(self):
        # Cast to 16 bit (needed for the fill filter to work)
        self.segImg  = sitk.Cast(self.segImg, sitk.sitkUInt16)

        self.dilateFilter.SetKernelRadius(2)
        self.segImg = self.dilateFilter.Execute(self.segImg, 0, 1, False)
        self.segImg = self.fillFilter.Execute(self.segImg)
        self.segImg = self.erodeFilter.Execute(self.segImg, 0, 1, False)

        return self

    def FindNewSeed(self):
    	# Find a new seed location nearby the current seed and within a 3 by 3 cube
    	# TO DO: Which is also within the expected bone intensity range (as defined by the sigmoid threshold)

    	print('self.seedPoint')
    	print(self.seedPoint)

    	# np.random.randint(6, size=3) gives a vector of 3 between 0 and 6
    	# Subtract 3 from each gives a random integer between -3 and 3
    	# Move the original seed point by this amount
    	self.seedPoint = [self.seedPoint_converted[0] + np.random.randint(6, size=3) - [3,3,3]]

    	
    	# Use the new seed to re-create the level set empty image to save the segmentation
    	self.InitializeLevelSet()

    def LeakageCheck(self):
        # Check the image type of self.segImg and image are the same (for Python 3.3 and 3.4)
        # self.segImg = sitk.Cast(self.segImg, segmentation.GetPixelID()) #Can't be a 32 bit float
        # self.segImg.CopyInformation(segmentation)

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

    	# Keep track of how many times the LeakageCheck has been run
    	self.LeakageCheck_iterations = self.LeakageCheck_iterations + 1


    	# If the LeakageCheck has ran more than 5 times choose a new seed location
    	# Within a 3 by 3 cube of the current seed location
    	if self.LeakageCheck_iterations >= 50000:
    		# Find a new nearby seed location
    		self.FindNewSeed()

    		# Re-run the level set initilization to re-create the edge potential map
    		# using the new seed location
    		self.InitializeLevelSet()

    		# Reset the leakage check iteration number to repeat this process every 5 interations
    		self.LeakageCheck_iterations = 0

        # Label Statistics Image Filter can't be 32-bit or 64-bit float
        self.segImg = sitk.Cast(self.segImg, sitk.sitkUInt16)

        # Fill any segmentation holes first
        start_time = timeit.default_timer() 

        elapsed = timeit.default_timer() - start_time

        if self.verbose == True:
            print(' ')
            print('FILLING elapsed : ' + str(round(elapsed,3)))
            print(' ')
               
        nda = sitk.GetArrayFromImage(self.segImg)
        nda = np.asarray(nda)

        pix_dims = np.asarray(self.original_image.GetSpacing())

        BoundingBoxFilter = sitk.LabelStatisticsImageFilter()

        # BoundingBoxFilter.Execute(self.original_image, self.segImg)
        # self.segImg = sitk.Cast(self.segImg, self.original_image.GetPixelID()) # Can't be 32-bit float
        BoundingBoxFilter.Execute(self.segImg, self.segImg)

        label = 1 # Only considering one bone in the segmentaiton for now

        BoundingBox = BoundingBoxFilter.GetBoundingBox(label)
        # Need to be consistent with how Crisco 2005 defines their bounding box
        z_size = BoundingBox[1] - BoundingBox[0] 
        x_size = BoundingBox[3] - BoundingBox[2]
        y_size = BoundingBox[5] - BoundingBox[4]

        # Convert to physical units (mm)
        x_size = x_size*pix_dims[0]
        y_size = y_size*pix_dims[1]
        z_size = z_size*pix_dims[2]

        volume = np.prod(pix_dims)*BoundingBoxFilter.GetCount(label)

        # Round to the nearest integer
        x_size = np.around(x_size,1)
        y_size = np.around(y_size,1)
        z_size = np.around(z_size,1)
        volume = np.rint(volume)

        # Check to see if the stop button has been pressed
        slicer.app.processEvents()
        if self.stop_segmentation == True:
        	return

        # Create a flag to determine whether the test failed
        # convergence_flag = 0 (passed), 1 (too large), 2 (too small)
       	convergence_flag = 0


        if self.verbose == True:
            print('x_size = ' + str(x_size))
            print('y_size = ' + str(y_size))
            print('z_size = ' + str(z_size))
            print('volume = ' + str(volume))

        if (volume > self.lower_range_volume) and (volume < self.upper_range_volume):
            if self.verbose == True:
                print('\033[97m' + "Passed with volume " + str(volume))                
        else:
            # Determine whether the segmentation was too large or too small
            if volume > self.upper_range_volume:
                convergence_flag = 1
            elif volume < self.lower_range_volume:
                convergence_flag = 2

            if self.verbose == True:
                print('\033[96m' + "Failed with volume " + str(volume))
                print('Expected range ' + str(self.lower_range_volume) + ' to ' + str(self.upper_range_volume))
      
        if (x_size > self.lower_range_x) and (x_size < self.upper_range_x):             
            if self.verbose == True:
                print('\033[97m' + "Passed x-bounding box " + str(x_size))
        else:
            if self.verbose == True:
             print('\033[96m' + "Failed x-bounding box " + str(x_size))

        if (y_size > self.lower_range_y) and (y_size < self.upper_range_y):            
            if self.verbose == True:
                print('\033[97m' + "Passed y-bounding box " + str(y_size))
        else:
            if self.verbose == True:
                print('\033[96m' + "Failed y-bounding box " + str(y_size))

        if (z_size > self.lower_range_z) and (z_size < self.upper_range_z):
            if self.verbose == True:
                print('\033[97m' + "Passed z-bounding box " + str(z_size))
        else:
            if self.verbose == True:
                print('\033[96m' + "Failed z-bounding box " + str(z_size))
                print('Expected range ' + str(self.lower_range_z) + ' to ' + str(self.upper_range_z))


        if convergence_flag == 1:
            # Segmentation was determined to be much too large. Lower number of iterations
            print(' ')
            print(' ')
            print('REDOING SEGMENTATION')

            # Check to see if the stop button has been pressed
            slicer.app.processEvents()
            if self.stop_segmentation == True:
            	return


            # Shape Detection Filter
            print('Current iterations = ' + str(self.GetShapeMaxIterations()))
            
            # Use 50% less iterations as currently used (since too large of a segmentation)
            # Use a random percent less iterations (between 10% and 60%) 
            # as are currently used (since too small of a segmentation)
            
            MaxIts = np.rint(self.GetShapeMaxIterations()*(1 - (np.random.rand(1)+0.10)/2))
            print('Decreasing iterations to = ' + str(MaxIts))
            self.SetShapeMaxIterations(MaxIts)

            if MaxIts < 10:
                print('Max Iterations of ' + str(MaxIts) + ' is too low! Stopping now.')
                return self

            # Don't need to redo the pre-processing steps
            start_time = timeit.default_timer() 
            self.SigmoidLevelSetIterations()
            elapsed = timeit.default_timer() - start_time

            if self.verbose == True:
                print('\033[92m' + 'Elapsed Time (processedImage):' + str(round(elapsed,3)))

            # Redo the leakage check (basically iteratively)
            self.LeakageCheck()


        elif convergence_flag == 2:
            # Segmentation was determined to be much too small. Increase number of iterations
            print(' ')
            print(' ')
            print('REDOING SEGMENTATION')

            # Check to see if the stop button has been pressed
            slicer.app.processEvents()
            if self.stop_segmentation == True:
            	return

            # Use a random percent more iterations (between 20% and 200%) 
            # as are currently used (since too small of a segmentation)
            MaxIts = np.rint(self.GetShapeMaxIterations()*(1 + (np.random.rand(1)+0.10)/2))

            print('Increasing iterations to = ' + str(MaxIts[0]))
            self.SetShapeMaxIterations(MaxIts)

            # Don't need to redo the pre-processing steps
            start_time = timeit.default_timer() 
            self.SigmoidLevelSetIterations()
            elapsed = timeit.default_timer() - start_time
            
            if self.verbose == True:
                print('\033[92m' + 'Elapsed Time (processedImage):' + str(round(elapsed,3)))
           
            if MaxIts > 3000:
                print('Max Iterations of ' + str(MaxIts) + ' is too high! Stopping now.')
                return self


           # Redo the leakage check (basically iteratively) using the new parameters
            self.LeakageCheck()



        return self

    def RoundSeedPoint(self):
		tempseedPoint = np.array(self.seedPoint).astype(int) # Just to be safe, make it int again
		tempseedPoint = tempseedPoint[0]

		# Convert from physical to image domain
		if self.convertSeedPhyscialFlag == True:

			# Check to see if the seed XY coordinates should be flipped (based on the checkmark in the GUI)
			if self.flip_seed_XY == False:
				tempFloat = [float(tempseedPoint[0]), float(tempseedPoint[1]), float(tempseedPoint[2])]
			else:
				# The image is not in the standard RAS orientation so the X and Y of the seed coordinates need to
				# Be flipped (the user has checked the checkmark in the user interface GUI)
				tempFloat = [float(tempseedPoint[0]), float(tempseedPoint[2]), float(tempseedPoint[1])]

			# Convert from physical units to voxel coordinates
			tempVoxelCoordinates = self.image.TransformPhysicalPointToIndex(tempFloat)

			print('tempVoxelCoordinates')
			print(tempVoxelCoordinates)

			# self.seedPoint = tempVoxelCoordinates


			self.seedPoint = tempFloat


			# Need to round the seedPoints because integers are required for indexing
			ScalingFactor = np.array(self.ScalingFactor)
			tempseedPoint = np.array(self.seedPoint).astype(int)
			tempseedPoint = abs(tempseedPoint)
			tempseedPoint = tempseedPoint/ScalingFactor # Scale the points down as well
			tempseedPoint = tempseedPoint.round() # Need to round it again for Python 3.3

		self.seedPoint = [tempseedPoint]
		self.original_seedPoint = [tempseedPoint]


		print('self.seedPoint')
		print(self.seedPoint)



		return self

    def UnCropImage(self):
        ' Indexing to put the segmentation of the cropped image back into the original MRI '

        # Need the original seed point to know where the cropped volume is in the original image
        cropNdxOne = np.asarray(self.original_seedPoint[0]) - self.searchWindow
        cropNdxTwo = np.asarray(self.original_seedPoint[0]) + self.searchWindow

        original_image_nda = sitk.GetArrayFromImage(self.original_image)
        original_image_nda = np.asarray(original_image_nda)

        seg_img_nda = sitk.GetArrayFromImage(self.segImg)
        seg_img_nda = np.asarray(seg_img_nda)

        original_image_nda = original_image_nda*0;

        original_image_nda[int(cropNdxOne[2]):int(cropNdxTwo[2]),
                        int(cropNdxOne[1]):int(cropNdxTwo[1]),
                        int(cropNdxOne[0]):int(cropNdxTwo[0])] = seg_img_nda

        # Convert back to SimpleITK image type
        self.segImg = sitk.Cast(sitk.GetImageFromArray(original_image_nda), sitk.sitkUInt16)
        self.segImg.CopyInformation(self.original_image)

        return self

    def CropImage(self):
        ' Crop the input_image around the initial seed point to speed up computation '
        cropFilter = sitk.CropImageFilter()
        addFilter  = sitk.AddImageFilter()

        im_size = np.asarray(self.image.GetSize())

        # Check to make sure the search window size won't go outside of the image dimensions
        for i in range(0,3):
            if self.searchWindow[i] > self.seedPoint[0][i]:
                self.searchWindow[i] = self.seedPoint[0][i]
            if self.searchWindow[i] > im_size[i] - self.seedPoint[0][i]:
                self.searchWindow[i] = im_size[i] - self.seedPoint[0][i]

        cfLowerBound = np.asarray(np.asarray(self.seedPoint[0]) - self.searchWindow, dtype=np.uint32)
        cfUpperBound = np.asarray(im_size - np.asarray(self.seedPoint[0]) - self.searchWindow, dtype=np.uint32)
        
        # These need to be changed to a list using numpy .tolist() for some reason
        cfLowerBound = cfLowerBound.tolist()
        cfUpperBound = cfUpperBound.tolist()
        
        cropFilter.SetLowerBoundaryCropSize(cfLowerBound)
        cropFilter.SetUpperBoundaryCropSize(cfUpperBound)

        self.image = cropFilter.Execute(self.image)

        # The seed point is now in the middle of the search window
        self.seedPoint = [np.asarray(self.searchWindow)]

        return self

    def PreprocessLevelSet(self):
        # Pre-processing for the level-set (e.g. create the edge map) only need to do once
        
        # self.sigFilter.SetBeta(120)
        # self.sigFilter.SetAlpha(0)

        processedImage  = self.sigFilter.Execute(self.image) 
        processedImage  = sitk.Cast(processedImage, sitk.sitkUInt16)

        edgePotentialFilter = sitk.EdgePotentialImageFilter()
        gradientFilter = sitk.GradientImageFilter()

        gradImage = gradientFilter.Execute(processedImage)

        processedImage = edgePotentialFilter.Execute(gradImage)

        ''' Create Seed Image '''
        if self.verbose == True:
            print('Starting ShapeDetectionLevelSetImageFilter')
            start_time = timeit.default_timer() 

        self.EdgePotentialMap = sitk.Cast(processedImage, sitk.sitkFloat32)

    def InitializeLevelSet(self):
    	# Use the seed location to initilize the level set image

        # Create the seed image
        nda = sitk.GetArrayFromImage(self.image)
        nda = np.asarray(nda)
        nda = nda*0
        seedPoint = self.seedPoint[0]

        print(seedPoint)
        print(seedPoint[0])
        print(seedPoint[1])
        print(seedPoint[2])

        # print('seedPoint')
        # print(seedPoint)

        # In numpy an array is indexed in the opposite order (z,y,x)
        nda[int(seedPoint[2])][int(seedPoint[1])][int(seedPoint[0])] = 1

        self.segImg = sitk.Cast(sitk.GetImageFromArray(nda), sitk.sitkUInt16)
        self.segImg.CopyInformation(self.image)

        self.segImg = sitk.BinaryDilate(self.segImg, 3)

        ''' Segmentation '''
        # Signed distance function using the initial seed point (segImg)
        init_ls = sitk.SignedMaurerDistanceMap(self.segImg, insideIsPositive=True, useImageSpacing=True)
        self.init_ls = sitk.Cast(init_ls, sitk.sitkFloat32)

    def SigmoidLevelSetIterations(self):
        ' Run the Shape Detection Level Set Segmentation Method'

        # sitk.Show(self.init_ls, 'self.init_ls')
        # sitk.Show(self.EdgePotentialMap, 'self.EdgePotentialMap')

        self.segImg = self.shapeDetectionFilter.Execute(self.init_ls, self.EdgePotentialMap)
     
        if self.verbose == True:
            print('Done with ShapeDetectionLevelSetImageFilter!')

        self.segImg = self.SegToBinary(self.segImg)
        
        return self

    def __init__(self):
        self.ScalingFactor = []
        self.AnisotropicIts = []
        self.AnisotropicTimeStep = []
        self.AnisotropicConductance = []
        self.ConfidenceConnectedIts = []
        self.ConfidenceConnectedMultiplier = []
        self.ConfidenceConnectedRadius = []
        self.BinaryMorphologicalRadius = []
        self.MaxVolume = []
        self.SeedListFilename = [] 
        self.SkipTresholdCalculation = False # Flag for running the sigmoid threshold calculation
        self.DilateImage = False # Flag for dilating the final segmentation result
        self.flip_seed_XY = False # Flag for flipping the XY coordinates of the seed location
        self.flip_sigmoid = False # Flag for segmenting bones which have a higher intensity than background (i.e. lighter)

        ## Initilize the ITK filters ##
        # Filters to down/up sample the image for faster computation
        self.shrinkFilter = sitk.ShrinkImageFilter()
        self.expandFilter = sitk.ExpandImageFilter()

        # Bias field correction
        self.BiasFilter = sitk.N4BiasFieldCorrectionImageFilter()

        # Filter to reduce noise while preserving edgdes
        self.anisotropicFilter = sitk.CurvatureAnisotropicDiffusionImageFilter()
        # Post-processing filters for fillinging holes and to attempt to remove any leakage areas
        self.dilateFilter = sitk.BinaryDilateImageFilter()
        self.erodeFilter = sitk.BinaryErodeImageFilter()
        self.fillFilter = sitk.BinaryFillholeImageFilter()  
        self.connectedComponentFilter = sitk.ScalarConnectedComponentImageFilter()
        self.laplacianFilter = sitk.LaplacianSegmentationLevelSetImageFilter()
        self.thresholdLevelSet = sitk.ThresholdSegmentationLevelSetImageFilter()

        # Initilize the SimpleITK Filters
        self.GradientMagnitudeFilter = sitk.GradientMagnitudeImageFilter()
        self.shapeDetectionFilter = sitk.ShapeDetectionLevelSetImageFilter()
        self.thresholdFilter = sitk.BinaryThresholdImageFilter()
        self.sigFilter = sitk.SigmoidImageFilter()

        # Set the deafult values 
        self.SetDefaultValues()

    def SetAnatomicalRelaxation(self, newRelaxation):
        self.AnatomicalRelaxation = newRelaxation
    def SetCurrentBone(self, newBone):
         self.current_bone = newBone

    def SetPatientGender(self, newGender):
        self.PatientGender= newGender

    def SetShapeMaxIterations(self, MaxIts):
        self.shapeDetectionFilter.SetNumberOfIterations(int(MaxIts))

    def GetShapeMaxIterations(self):
        MaxIts = self.shapeDetectionFilter.GetNumberOfIterations()
        return MaxIts

    # def SetSearchWindowSize(self, searchWindow):
    #     self.searchWindow = [searchWindow, searchWindow, searchWindow]

    def SetShapePropagationScale(self, propagationScale):
        self.shapeDetectionFilter.SetPropagationScaling(-1*propagationScale)

    def SetShapeCurvatureScale(self, curvatureScale):
        self.shapeDetectionFilter.SetCurvatureScaling(curvatureScale)

    def SetShapeMaxRMSError(self, MaxRMSError):
        self.shapeDetectionFilter.SetMaximumRMSError(MaxRMSError)

    def SetLevelSetCurvature(self, curvatureScale):
        self.thresholdLevelSet.SetCurvatureScaling(curvatureScale)
        
    def SetLevelSetPropagation(self, propagationScale):
        self.thresholdLevelSet.SetPropagationScaling(propagationScale)
        
    def SetLevelSetLowerThreshold(self, lowerThreshold):
        self.sigFilter.SetBeta(int(lowerThreshold))
        self.thresholdFilter.SetLowerThreshold(int(lowerThreshold)+1) # Add one so the threshold is greater than Zero
        self.thresholdLevelSet.SetLowerThreshold(int(lowerThreshold))   


    def SetLevelSetUpperThreshold(self, upperThreshold):
        self.sigFilter.SetAlpha(int(upperThreshold))
        self.thresholdFilter.SetUpperThreshold(int(upperThreshold))

        self.thresholdLevelSet.SetUpperThreshold(int(upperThreshold))   
        
    def SetLevelSetError(self,MaxError):        
        self.thresholdLevelSet.SetMaximumRMSError(MaxError)

    def SetImage(self, image):
        self.image = image

    def SefSeedPoint(self, SeedPoint):
        self.SeedPoint = SeedPoint

    def SetScalingFactor(self, ScalingFactor):
        ScalingFactor = [int(ScalingFactor),int(ScalingFactor),int(ScalingFactor)]
        self.ScalingFactor = ScalingFactor
        self.shrinkFilter.SetShrinkFactors(ScalingFactor)
        self.expandFilter.SetExpandFactors(ScalingFactor)

    def SetAnisotropicIts(self, AnisotropicIts):
        self.anisotropicFilter.SetNumberOfIterations(int(AnisotropicIts))
    
    def SetAnisotropicTimeStep(self, AnisotropicTimeStep):
        self.anisotropicFilter.SetTimeStep(AnisotropicTimeStep)
    
    def SetAnisotropicConductance(self, AnisotropicConductance):
        self.anisotropicFilter.SetConductanceParameter(AnisotropicConductance)

    def SetConfidenceConnectedIts(self, ConfidenceConnectedIts):
        self.ConfidenceConnectedIts = ConfidenceConnectedIts

    def SetConfidenceConnectedMultiplier(self, ConfidenceConnectedMultiplier):
        self.ConfidenceConnectedMultiplier = ConfidenceConnectedMultiplier

    def SetConfidenceConnectedRadius(self, ConfidenceConnectedRadius):
        self.ConfidenceConnectedRadius = ConfidenceConnectedRadius

    def SetBinaryMorphologicalRadius(self, kernelRadius):
        self.erodeFilter.SetKernelRadius(kernelRadius)
        self.dilateFilter.SetKernelRadius(kernelRadius) 

    def SetMaxVolume(self, MaxVolume):
        self.MaxVolume = MaxVolume  

    def SetLaplacianExpansionDirection(self, expansionDirection):       
        self.laplacianFilter.SetReverseExpansionDirection(expansionDirection)

    def SetLaplacianError(self, RMSError):
        self.laplacianFilter.SetMaximumRMSError(RMSError)

    def SetConnectedComponentFullyConnected(self, fullyConnected):
        self.connectedComponentFilter.SetFullyConnected(fullyConnected) 

    def SetConnectedComponentDistance(self, distanceThreshold):
        #Distance = Intensity difference NOT location distance
        self.connectedComponentFilter.SetDistanceThreshold(distanceThreshold) 
   
    def EstimateSigmoid(self):
        ''' Estimate the upper threshold of the sigmoid based on the 
        mean and std of the image intensities '''
        ndaImg = sitk.GetArrayFromImage(self.image)

        # [ndaImg > 25]
        std = np.std(ndaImg) # 30 25
        mean = np.mean(ndaImg)

        # Using a linear model (fitted in Matlab and manually selected sigmoid threshold values)
        # UpperThreshold = 0.899*(std+mean) - 41.3

        UpperThreshold = 0.002575*(std+mean)*(std+mean) - 0.028942*(std+mean) + 36.791614

        if self.verbose == True:
            print('Mean: ' + str(round(mean,2)))
            print('STD: ' + str(round(std,2)))
            print('UpperThreshold: ' + str(round(UpperThreshold,2)))
            print(' ')

        return UpperThreshold

    def FlipImage(self,image):
        #Flip image(s) (if needed)
        flipFilter = sitk.FlipImageFilter()
        flipFilter.SetFlipAxes((False,True,False))
        image = flipFilter.Execute(self.image)
        return image

    def ThresholdImage(self):
        try:
            self.segImg.CopyInformation(self.image)
        except:
            print('Error in copying information from self.image')
        tempImg = self.segImg * self.image
        self.segImg = self.thresholdFilter.Execute(tempImg)
        return self
    
    def scaleDownImage(self):
        self.image = self.shrinkFilter.Execute(self.image)
        return self

    def scaleUpImage(self):
        self.segImg = self.expandFilter.Execute(self.segImg)
        return self

    # Function definitions are below
    def apply_AnisotropicFilter(self):
        self.image = self.anisotropicFilter.Execute(self.image)
        return self

    def savePointList(self):
        try:
            # Save the user defined points in a .txt for automatimating testing (TODO)
            text_file = open(self.SeedListFilename, "r+")
            text_file.readlines()
            text_file.write("%s\n" % self.seedPoint)
            text_file.close()
        except:
            print("Saving to .txt failed...")
        return

    def AddImages(self, imageOne, imageTwo, iteration_num):

        ndaOutput = sitk.GetArrayFromImage(imageOne)
        ndaOutput = np.asarray(ndaOutput) 
        ndaTwo = sitk.GetArrayFromImage(imageTwo)

        ndaTwo = np.asarray(ndaTwo) 
        ndaTwo[ndaTwo != 0] = iteration_num

        ndaOutput = ndaOutput + ndaTwo
        output = sitk.Cast(sitk.GetImageFromArray(ndaOutput), imageOne.GetPixelID())
        output.CopyInformation(imageOne)

        return output

    def SegToBinary(self, image):
        # Want 0 for the background and 1 for the objects
        nda = sitk.GetArrayFromImage(image)
        nda = np.asarray(nda)

        nda[nda < 0] = 0
        nda[nda != 0] = 1
        
        image = sitk.Cast(sitk.GetImageFromArray(nda), self.image.GetPixelID())
        image.CopyInformation(self.image)

        return image


    def BiasFieldCorrection(self): 
        if self.verbose == True:
            print('\033[94m' + 'Bias Field Correction')

        #   Correct for the MRI bias field 
        self.image  = sitk.Cast(self.image, sitk.sitkFloat32)

        input_image_nda = sitk.GetArrayFromImage(self.image)
        input_image_nda = np.asarray(input_image_nda)
        input_image_nda = input_image_nda*0

        mask_img = sitk.Cast(sitk.GetImageFromArray(input_image_nda), sitk.sitkFloat32)
        mask_img.CopyInformation(self.image)

        # test = sitk.OtsuThreshold( self.image, 0, 1, 200 )

        mask_img = sitk.Cast(mask_img, 1) #Can't be a 32 bit float

        print(mask_img.GetPixelID())


        self.image = self.BiasFilter.Execute(self.image, mask_img)
        sitk.Show(self.image, 'post_bias')


if __name__ == "__main__":
    # TODO: need a way to access and parse command line arguments
    # TODO: ideally command line args should handle --xml

    import sys
    print(sys.argv)


#############################################################################################
###MULTIPROCESSOR HELPER CLASS###
#############################################################################################

class Multiprocessor(object):
    """Helper class for seperating a segmentation class (such as from SimpleITK) into
    several logical cores in parallel. Requires: SegmentationClass, Seed List, SimpleITK Image"""
    def __init__(self):
        self = self

    def Execute(self, seedList, MRI_Image, parameters, numCPUS, outputSelector, verbose = False):
		self.seedList = seedList
		self.MRI_Image = MRI_Image
		self.parameters = parameters
		self.numCPUS = numCPUS
		self.verbose = verbose #Print output text to terminal or not
		self.outputSelector = outputSelector # For updating the view between each bone

		#Convert to voxel coordinates
		self.RoundSeedPoints() 

		#Create an empty segmentationLabel image
		nda = sitk.GetArrayFromImage(self.MRI_Image)
		nda = np.asarray(nda)
		nda = nda*0
		segmentationLabel = sitk.Cast(sitk.GetImageFromArray(nda), self.MRI_Image.GetPixelID())
		segmentationLabel.CopyInformation(self.MRI_Image)

		for x in range(len(seedList)):
			slicer.app.processEvents()

			# Only run the segmentation function if the stop button in the GUI is set to false
			tempOutput = self.RunSegmentation(seedList[x], x)
			# tempOutput = sitk.Cast(sitk.GetImageFromArray(tempOutput), self.MRI_Image.GetPixelID())
			# tempOutput.CopyInformation(self.MRI_Image)
			# segmentationLabel = segmentationLabel + tempOutput

			try:
				tempOutput = sitk.Cast(sitk.GetImageFromArray(tempOutput), self.MRI_Image.GetPixelID())
				tempOutput.CopyInformation(self.MRI_Image)

				segmentationLabel = segmentationLabel + tempOutput

				# Convert segmentationArray back into an image
				# temp_segmentationLabel = sitk.Cast(sitk.GetImageFromArray(segmentationLabel), self.MRI_Image.GetPixelID())
				# temp_segmentationLabel.CopyInformation(self.MRI_Image)

				# Output options in Slicer = {0:'background', 1:'foreground', 2:'label'}
				imageID = self.outputSelector.currentNode()
				sitkUtils.PushVolumeToSlicer(segmentationLabel, targetNode=imageID,name=imageID.GetName(), className='vtkMRMLLabelMapVolumeNode')
				slicer.util.setSliceViewerLayers(background='keep-current', foreground='keep-current', label=imageID, foregroundOpacity=None, labelOpacity=1)
				slicer.app.processEvents()
			except:
				# The stop button was pressed
				pass

		return segmentationLabel

    def RunSegmentation(self, SeedPoint, ndx):
        """ Function to be used with the Multiprocessor class (needs to be its own function 
            and not part of the same class to avoid the 'Pickle' type errors. """
        # segmentationClass = BoneSeg()

        # Change some parameters(s) of the segmentation class for the optimization
        # Parameters = [LevelSet Thresholds, LevelSet Iterations, Level Set Error, Shape Level Set Curvature, Shape Level Set Max Error, Shape Level Set Max Its]
        print(self.parameters)
        # segmentationClass.SetLevelSetLowerThreshold(self.parameters[0][0])
        # segmentationClass.SetLevelSetUpperThreshold(self.parameters[0][1])


        # parameters = [self.ShapeCurvatureScale, self.ShapeMaxRMSError, self.ShapeMaxIts, 
        #                 self.ShapePropagationScale, self.selected_gender, self.BonesSelected, self.RelaxationAmount] 


        # Shape Detection Filter
        self.segmentationClass.SetShapeCurvatureScale(self.parameters[0])
        self.segmentationClass.SetShapeMaxRMSError(self.parameters[1])
        self.segmentationClass.SetShapeMaxIterations(self.parameters[2])
        self.segmentationClass.SetShapePropagationScale(self.parameters[3])
        self.segmentationClass.SetPatientGender(self.parameters[4])
        self.segmentationClass.SetCurrentBone(self.parameters[5][ndx])
        self.segmentationClass.SetAnatomicalRelaxation(self.parameters[6])
        self.segmentationClass.SetAnisotropicIts(self.parameters[7])
        self.segmentationClass.DilateImage = self.parameters[8]


        # Only set the sigmoid filter threshold if the user selected on (not equal to the default of zero)
        if self.parameters[8] != 0:
        	
        	self.segmentationClass.SkipTresholdCalculation = True

        	# Check to see if we are segmenting bright or dark bones
        	# Essentially, just flip the lower and upper threshold of the levelset
        	if self.segmentationClass.flip_sigmoid == False: 
        		self.segmentationClass.SetLevelSetLowerThreshold(self.parameters[9])
        		self.segmentationClass.SetLevelSetUpperThreshold(0)
        	else:
        		self.segmentationClass.SetLevelSetLowerThreshold(0)
        		self.segmentationClass.SetLevelSetUpperThreshold(self.parameters[9])



        # segmentation = self.segmentationClass.Execute(self.MRI_Image,[SeedPoint])
        segmentation = self.segmentationClass.Execute(self.MRI_Image, [SeedPoint], verbose=True, 
                                    returnSitkImage=False, convertSeedPhyscialFlag=False)


        print('DONE WITH SEGMENTATION!')

        return segmentation

    def RoundSeedPoints(self):           
        seeds = []
        for i in range(0,len(self.seedList)): #Select which bone (or all of them) from the csv file
            #Convert from string to float
            # tempFloat = [float(self.seedList[i][0])/(-0.24), float(self.seedList[i][1])/(-0.24), float(self.seedList[i][2])/(0.29)]
            tempFloat = [float(self.seedList[i][0]), float(self.seedList[i][1]), float(self.seedList[i][2])]
            
            #Convert from physical units to voxel coordinates
            tempVoxelCoordinates = self.MRI_Image.TransformPhysicalPointToContinuousIndex(tempFloat)
            seeds.append(tempVoxelCoordinates)

        self.seedList = seeds
        return self




